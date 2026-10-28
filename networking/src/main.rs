//! One native Iroh endpoint per Centaur data directory. Private Unix-socket
//! control clients request bounded loopback tunnels carrying the existing
//! certificate-pinned TLS protocol. No project or provider secrets are decoded
//! here; the authoritative Qt host continues to authorise every action.
use anyhow::{Context, Result, ensure};
use fs2::FileExt;
use iroh::{
    Endpoint, EndpointAddr, EndpointId, RelayMode, SecretKey,
    endpoint::{Connection, presets},
};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    net::SocketAddr,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::Duration,
};
use tokio::{
    io::{AsyncBufReadExt, AsyncRead, AsyncWriteExt, BufReader},
    net::{TcpListener, TcpStream, UnixListener, UnixStream},
    sync::{Mutex, Semaphore, watch},
    task::JoinHandle,
    time::timeout,
};

const ALPN: &[u8] = b"centaur/collaboration/2";
const PREFACE: &[u8; 4] = b"CTR2";
const MAX_CONTROL: usize = 16 * 1024;
type Target = Option<(u64, u16)>;
type Output = Arc<Mutex<tokio::net::unix::OwnedWriteHalf>>;

#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "camelCase", deny_unknown_fields)]
enum Command {
    Info,
    Listen {
        port: u16,
    },
    Unlisten,
    Connect {
        request: u64,
        node: String,
        #[serde(default)]
        relay: Option<String>,
        #[serde(default)]
        addresses: Vec<String>,
    },
    Disconnect,
}

fn identity(folder: &Path) -> Result<SecretKey> {
    let path = folder.join("iroh.key");
    match fs::read(&path) {
        Ok(bytes) => {
            let raw: [u8; 32] = bytes.try_into().map_err(|_| {
                anyhow::anyhow!("Invalid Iroh identity; restore its key rather than replacing it")
            })?;
            fs::set_permissions(&path, fs::Permissions::from_mode(0o600))?;
            Ok(SecretKey::from_bytes(&raw))
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            let secret = SecretKey::generate();
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .mode(0o600)
                .open(path)?;
            file.write_all(&secret.to_bytes())?;
            file.sync_all()?;
            Ok(secret)
        }
        Err(error) => Err(error.into()),
    }
}

async fn endpoint(secret: SecretKey) -> Result<Endpoint> {
    let local = std::env::var_os("CENTAUR_IROH_LOCAL").is_some();
    let mut builder = if local {
        Endpoint::builder(presets::Minimal)
            .relay_mode(RelayMode::Disabled)
            .clear_ip_transports()
            .bind_addr("127.0.0.1:0")?
    } else {
        Endpoint::builder(presets::N0)
    };
    if std::env::var_os("CENTAUR_IROH_RELAY_ONLY").is_some() {
        ensure!(!local, "Local-only and relay-only modes cannot be combined");
        builder = builder.clear_ip_transports();
    }
    Ok(builder
        .secret_key(secret)
        .alpns(vec![ALPN.to_vec()])
        .bind()
        .await?)
}

fn info(endpoint: &Endpoint) -> Value {
    let addr = endpoint.addr();
    json!({"event":"ready", "version":1, "node":endpoint.id().to_string(),
        "relay":addr.relay_urls().next().map(ToString::to_string),
        "addresses":addr.ip_addrs().take(16).map(ToString::to_string).collect::<Vec<_>>()})
}

fn address(node: &str, relay: Option<&str>, addresses: &[String]) -> Result<EndpointAddr> {
    ensure!(
        node.len() == 64 && addresses.len() <= 16,
        "Invalid endpoint address"
    );
    let id: EndpointId = node.parse()?;
    let mut result = EndpointAddr::new(id);
    if let Some(relay) = relay {
        ensure!(
            relay.len() <= 256 && relay.starts_with("https://"),
            "Invalid relay URL"
        );
        let url: iroh::RelayUrl = relay.parse()?;
        ensure!(
            url.username().is_empty()
                && url.password().is_none()
                && url.query().is_none()
                && url.fragment().is_none(),
            "Invalid relay URL"
        );
        result = result.with_relay_url(url);
    }
    for address in addresses {
        let ip: SocketAddr = address.parse()?;
        ensure!(
            ip.port() != 0 && !ip.ip().is_unspecified() && !ip.ip().is_multicast(),
            "Invalid direct address"
        );
        result = result.with_ip_addr(ip);
    }
    Ok(result)
}

async fn emit(output: &Output, event: Value) -> Result<()> {
    let mut bytes = serde_json::to_vec(&event)?;
    bytes.push(b'\n');
    timeout(
        Duration::from_secs(5),
        output.lock().await.write_all(&bytes),
    )
    .await??;
    Ok(())
}

async fn line<R: AsyncRead + Unpin>(reader: &mut BufReader<R>) -> Result<Option<Vec<u8>>> {
    let mut bytes = Vec::new();
    loop {
        let chunk = reader.fill_buf().await?;
        if chunk.is_empty() {
            ensure!(bytes.is_empty(), "Incomplete control frame");
            return Ok(None);
        }
        let count = chunk
            .iter()
            .position(|b| *b == b'\n')
            .map_or(chunk.len(), |n| n + 1);
        ensure!(
            bytes.len() + count <= MAX_CONTROL,
            "Control frame too large"
        );
        bytes.extend_from_slice(&chunk[..count]);
        reader.consume(count);
        if bytes.last() == Some(&b'\n') {
            return Ok(Some(bytes));
        }
    }
}

async fn pump(
    connection: Connection,
    mut tcp: TcpStream,
    mut send: iroh::endpoint::SendStream,
    mut recv: iroh::endpoint::RecvStream,
) -> Result<()> {
    let (mut read, mut write) = tcp.split();
    // Preserve the final TLS rejection/revocation bytes when a socket closes.
    // A QUIC connection close can discard queued stream data; finish the stream
    // and wait for acknowledgement before releasing the connection instead.
    let upstream = async {
        tokio::io::copy(&mut read, &mut send).await?;
        send.finish()?;
        let _ = send.stopped().await?;
        Ok::<_, anyhow::Error>(())
    };
    let downstream = async {
        tokio::io::copy(&mut recv, &mut write).await?;
        write.shutdown().await?;
        Ok::<_, anyhow::Error>(())
    };
    tokio::try_join!(upstream, downstream)?;
    connection.close(0u32.into(), b"tunnel closed");
    Ok(())
}

async fn outgoing(
    endpoint: Endpoint,
    addr: EndpointAddr,
    output: Output,
    request: u64,
    _permit: tokio::sync::OwnedSemaphorePermit,
) -> Result<()> {
    let connection = timeout(Duration::from_secs(30), endpoint.connect(addr, ALPN)).await??;
    let (mut send, recv) = connection.open_bi().await?;
    // Opening a QUIC stream alone does not make it visible to accept_bi().
    send.write_all(PREFACE).await?;
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    emit(
        &output,
        json!({"event":"tunnel", "request":request, "port":listener.local_addr()?.port()}),
    )
    .await?;
    let (tcp, _) = timeout(Duration::from_secs(10), listener.accept()).await??;
    pump(connection, tcp, send, recv).await
}

async fn client(
    stream: UnixStream,
    endpoint: Endpoint,
    target: watch::Sender<Target>,
    id: u64,
    slots: Arc<Semaphore>,
) -> Result<()> {
    let (read, write) = stream.into_split();
    let output = Arc::new(Mutex::new(write));
    let mut reader = BufReader::new(read);
    let mut tunnel: Option<JoinHandle<()>> = None;
    let result: Result<()> = async {
        emit(&output, info(&endpoint)).await?;
        while let Some(bytes) = line(&mut reader).await? {
            match serde_json::from_slice::<Command>(&bytes)? {
                Command::Info => emit(&output, info(&endpoint)).await?,
                Command::Listen { port } => {
                    ensure!(port != 0, "Invalid local port");
                    let current = *target.borrow();
                    ensure!(current.is_none() || current.is_some_and(|value| value.0 == id), "Another host owns the listener");
                    target.send_replace(Some((id, port)));
                    emit(&output, info(&endpoint)).await?;
                }
                Command::Unlisten => { if target.borrow().is_some_and(|value| value.0 == id) { target.send_replace(None); } }
                Command::Disconnect => { if let Some(task) = tunnel.take() { task.abort(); } }
                Command::Connect { request, node, relay, addresses } => {
                    if let Some(task) = tunnel.take() { task.abort(); }
                    let addr = address(&node, relay.as_deref(), &addresses)?;
                    let permit = slots.clone().try_acquire_owned().context("Too many connections")?;
                    let endpoint = endpoint.clone(); let output = output.clone();
                    tunnel = Some(tokio::spawn(async move {
                        if outgoing(endpoint, addr, output.clone(), request, permit).await.is_err() {
                            let _ = emit(&output, json!({"event":"error", "request":request, "message":"Could not reach the project host through Iroh"})).await;
                        } else { let _ = emit(&output, json!({"event":"closed", "request":request})).await; }
                    }));
                }
            }
        }
        Ok(())
    }.await;
    if let Some(task) = tunnel {
        task.abort();
    }
    if target.borrow().is_some_and(|value| value.0 == id) {
        target.send_replace(None);
    }
    result
}

struct SocketFile(PathBuf);
impl Drop for SocketFile {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() -> Result<()> {
    let args: Vec<_> = std::env::args_os().collect();
    ensure!(
        args.len() == 3 && args[1] == "--state-dir",
        "Usage: centaur-network --state-dir DIRECTORY"
    );
    let folder = PathBuf::from(&args[2]);
    fs::create_dir_all(&folder)?;
    fs::set_permissions(&folder, fs::Permissions::from_mode(0o700))?;
    let lock = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .open(folder.join("iroh.lock"))?;
    if lock.try_lock_exclusive().is_err() {
        return Ok(());
    }
    let path = folder.join("iroh.sock");
    match fs::remove_file(&path) {
        Ok(()) => {}
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
        Err(e) => return Err(e.into()),
    }
    let listener =
        UnixListener::bind(&path).context("Could not create the private networking socket")?;
    let _socket_file = SocketFile(path.clone());
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600))?;
    let endpoint = endpoint(identity(&folder)?).await?;
    let (target, _) = watch::channel::<Target>(None);
    let slots = Arc::new(Semaphore::new(24));
    let controls = Arc::new(Semaphore::new(64));
    let serial = AtomicU64::new(1);
    let mut idle = tokio::time::interval(Duration::from_secs(5));
    let mut idle_ticks = 0;
    loop {
        tokio::select! {
            accepted = listener.accept() => {
                let (stream, _) = accepted?;
                if let Ok(permit) = controls.clone().try_acquire_owned() {
                    let endpoint = endpoint.clone(); let target = target.clone(); let slots = slots.clone(); let id = serial.fetch_add(1, Ordering::Relaxed);
                    tokio::spawn(async move { let _permit = permit; let _ = client(stream, endpoint, target, id, slots).await; });
                }
            }
            incoming = endpoint.accept() => {
                let Some(incoming) = incoming else { break; };
                let Some(owner) = *target.borrow() else { incoming.refuse(); continue; };
                let Ok(permit) = slots.clone().try_acquire_owned() else { incoming.refuse(); continue; };
                let mut target = target.subscribe();
                tokio::spawn(async move {
                    let _permit = permit;
                    let forwarding = async {
                        let connection = timeout(Duration::from_secs(10), incoming).await??;
                        let (send, mut recv) = timeout(Duration::from_secs(10), connection.accept_bi()).await??;
                        let mut preface = [0; 4]; timeout(Duration::from_secs(5), recv.read_exact(&mut preface)).await??;
                        ensure!(&preface == PREFACE, "Invalid protocol preface");
                        let tcp = TcpStream::connect((std::net::Ipv4Addr::LOCALHOST, owner.1)).await?;
                        pump(connection, tcp, send, recv).await
                    };
                    tokio::pin!(forwarding);
                    tokio::select! {
                        _ = &mut forwarding => {},
                        _ = target.changed() => { let _ = timeout(Duration::from_secs(10), &mut forwarding).await; }
                    }
                });
            }
            _ = idle.tick() => {
                if controls.available_permits() == 64 { idle_ticks += 1; } else { idle_ticks = 0; }
                if idle_ticks >= 3 { break; }
            }
            _ = tokio::signal::ctrl_c() => break,
        }
    }
    endpoint.close().await;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn oversized_and_incomplete_control_frames_are_rejected() {
        let data = vec![b'x'; MAX_CONTROL + 1];
        assert!(line(&mut BufReader::new(data.as_slice())).await.is_err());
        assert!(line(&mut BufReader::new(&b"{}"[..])).await.is_err());
        assert!(
            line(&mut BufReader::new(&b"{}\n"[..]))
                .await
                .unwrap()
                .is_some()
        );
    }
    #[test]
    fn persisted_identity_is_private_and_corruption_fails_closed() {
        let folder = std::env::temp_dir().join(format!(
            "centaur-identity-test-{}",
            SecretKey::generate().public()
        ));
        fs::create_dir(&folder).unwrap();
        let first = identity(&folder).unwrap();
        assert_eq!(first.public(), identity(&folder).unwrap().public());
        let path = folder.join("iroh.key");
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        fs::write(&path, b"corrupt").unwrap();
        assert!(identity(&folder).is_err());
        assert_eq!(fs::read(&path).unwrap(), b"corrupt");
        fs::remove_dir_all(folder).unwrap();
    }
    #[test]
    fn endpoint_addresses_are_typed_and_bounded() {
        let node = SecretKey::generate().public().to_string();
        assert!(address(&node, None, &["127.0.0.1:1234".into()]).is_ok());
        assert!(address(&node, Some("http://example.com"), &[]).is_err());
        assert!(address(&node, Some("https://user:secret@example.com"), &[]).is_err());
        assert!(address(&node, None, &["0.0.0.0:1234".into()]).is_err());
        assert!(address("invalid", None, &[]).is_err());
    }
}
