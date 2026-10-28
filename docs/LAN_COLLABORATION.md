# Collaborate across computers and networks

Centaur 0.3 adds Iroh peer-to-peer connectivity alongside the existing LAN transport. Both computers need the current Centaur package; only the project host needs OMP installed and signed in. The package bundles the native networking helper, so participants do not need Rust, Cargo, a separate Iroh installation or a cloud account.

## Update and launch

Use the [precompiled installation and update commands](BINARY_DISTRIBUTION.md) on the Intel NixOS Air and ARM64 NixOS VM. Wait for both Publish jobs for the chosen commit to succeed. Close older windows and stop the old background host before updating. Launch the installed profile from a graphical Linux session:

```sh
CENTAUR_AGENT="$HOME/.local/bin/omp" \
  "$HOME/.local/state/nix/profiles/centaur/bin/centaur" --demo
```

The guest can omit `CENTAUR_AGENT`. An existing shortcut using this profile also works. Look for **v0.3.0** with a source identifier in the chat footer or Settings.

The app starts `centaur-host` automatically as a background process for its data directory. It coordinates local windows, stores projects and runs OMP. Sharing resumes when that host restarts. Closing a Centaur window stops its preview but leaves the background host running. The host computer must remain awake and connected. No system service installation is required.

## Invite someone over Iroh (default)

1. Open a project and choose **Invite**, beside Deploy.
2. Leave **Local network only** unchecked and choose **Create invitation**.
3. Choose **Copy invitation** and send the complete code privately to one participant.
4. Create a separate invitation for each additional person. Each code is single-use and expires after 20 minutes.

The `centaur2:` invitation identifies the host by its persistent Iroh public identity and pinned TLS certificate, rather than a manually entered IP address. Iroh tries direct paths and can use the default n0 relays when necessary. The relay carries encrypted traffic and cannot read the project conversation or provider credentials. Network restrictions or unavailable relay/discovery services can still prevent connections; Iroh is not an always-available hosted project service.

For this mode, no incoming TCP firewall rule, UTM forwarding or router configuration is normally needed. The helper opens outbound connections and uses a private loopback-only TLS listener. Different Centaur data directories have independent identities and helpers. Several local windows share the same helper/endpoint for their data directory; it exits after its last local client closes and a short idle grace period.

## Optional: local network only

Check **Local network only**, enter the host's reachable IPv4 address, and create an invitation. This produces the existing `centaur1:` code. Existing LAN invitations, memberships and cached projects remain usable after upgrading; LAN and Iroh participants can contribute to the same project.

Only this legacy mode uses incoming TCP port **43177** by default. On the host's NixOS configuration, add that port while preserving other allowed ports:

```nix
networking.firewall.allowedTCPPorts = [ 43177 ];
```

Apply with your normal NixOS rebuild procedure. A VM's internal address may not be reachable from a physical computer; LAN mode may require a reachable VM network or port forwarding. Opening the guest firewall alone does not change VM reachability. Iroh mode avoids this manual address/port setup in typical networks. This implementation does not change UTM or control its mouse.

## Join a project

1. In Projects, choose **Join project**.
2. Enter your name and paste the complete invitation code.
3. Read the trust notice and choose **Join project**. Shared native QML executes on your device, so join only a host you trust.
4. The project opens with its conversation, drawings and current app. It also appears as a shared card in Projects and reconnects on later launches.

Names are assigned to stable participant credentials. If a name is already used in the project, the host adds a suffix rather than merging two identities. Reconnecting reuses the assigned name and identity. Changing this device's local display name does not change an existing shared identity. There are no cloud accounts yet.

## Work together

Both Interact and Build retain chat. Messages, sketches, Comment arrows, conflict proposals and accepted app source synchronise. Each computer renders a separate native preview; ticking a checkbox or typing inside one preview does not synchronise that app's runtime data.

Only the host invokes OMP, checks proposed QML and saves source history. Compatible requests apply automatically. Agent mentions are queued; ordinary chat can continue while the agent works. New explicit agent directions and changed sketches invalidate stale work, which is retried against the latest conversation. Only the affected authors approve an actual conflict. Stop clears the selected project's pending requests.

The guest receives accepted `App.qml`, recent conversation/decisions and annotation state for the invited project. It does not receive other projects, Git directories, host filesystem paths, provider credentials or the host's private data directory. The current generated-app contract remains one QML file using built-in Qt modules and bundled fonts; arbitrary assets or compiled projects are not distributed by this milestone.

## Disconnection, leaving and access

When the host becomes unreachable, the guest shows a connection status and reconnects automatically. Cached app source remains usable locally. Sending and drawing are disabled while disconnected; an unsent chat draft remains in the composer. Actions already saved for transmission are retried with sequence numbers, so an acknowledgement lost during a disconnect does not duplicate the accepted action. A stale drawing or conflict vote is rejected if the app changed before it arrived.

For this prototype, each project has one editable guest window per device. Additional windows show the same project read-only; closing the editing window lets another take over automatically. This protects the device’s pending-action queue from competing writers. Different devices can all contribute at once.

A guest's project-card menu offers **Leave project**, with confirmation. This removes that device's saved membership without deleting the owner's project. Rename, archive, deletion and invitations are owner actions. To return after leaving, request a new invitation.

For either transport, the owner can choose **Stop sharing** in Invite. This revokes all invitations and participant credentials for that project and disconnects its guests. Existing copies of app source on a guest cannot be remotely erased. Owners can start sharing again with fresh invitations. Individual-member removal is not implemented yet.

## Background host maintenance

The host keeps the OMP executable/model environment from when it was launched. After changing that environment or updating Centaur, close local windows and restart the background host before reopening the app. From a local repository checkout, with the same data directory used by Centaur:

```sh
nix build
./result/bin/centaur-host --stop --data-dir "$HOME/.local/share/Centaur/Centaur"
```

If you used `--data-dir`, substitute that directory. On the next launch, Centaur starts the updated host with the launcher's environment. Do not stop a host while collaborators are actively working. No automatic transfer to a different host is provided.

## Storage and transport

- Original projects and history stay under `projects/<id>` on the host.
- TLS certificate, private key, persistent `iroh.key` and hashed invitation/member credentials live in the host's owner-only `network/` directory.
- Guests store their credential, pending actions, cached state and `App.qml` under an owner-only `shared/<id>/` directory. Leaving removes the credential; cached source remains for recovery.
- The invitation contains the host certificate's SHA-256 fingerprint. The client checks that fingerprint before sending any invitation or member credential. A changed certificate stops reconnection and requires a fresh invitation.
- The application protocol remains bounded newline-delimited JSON over pinned TLS 1.2 or later, with protocol version 1. Iroh carries those TLS bytes over a dedicated `centaur/collaboration/2` QUIC stream. The host authorises each project/action and assigns author identity from the credential. Sequence acknowledgements are persisted with accepted project mutations.

TLS uses Qt Network's socket API; see [Qt SSL sockets](https://doc.qt.io/qt-6/qsslsocket.html). Iroh uses the n0 endpoint lookup and relay services. This version has no mobile client, automatic host failover, offline editing or sandbox for untrusted native QML.

## Two-machine acceptance test

1. Update both machines. Start the host with its working OMP environment.
2. Invite the second machine. Verify the project card and assigned name on the guest.
3. Exchange chat and drawings in both directions, including while Interact is selected.
4. Make an agent request from the guest. Check that the host's OMP handles it and both native previews receive the accepted change.
5. Send ordinary chat during a request, then queue a second agent request. Both should be retained and completed.
6. Give incompatible directions and check that only the affected authors must agree.
7. Close the owner's UI window. The guest should still be able to chat and request an app change.
8. Disconnect/reconnect the guest's network. Check status, retained draft, eventual source catch-up and absence of duplicated messages.
9. Test Leave and Stop sharing. Unrelated host projects must never appear on the guest.

## Internet acceptance test

After the automated checks pass, update both NixOS machines to the same published v0.3 build:

1. Repeat the two-machine test above using the default Iroh invitation. It should require no host-address entry or incoming TCP rule.
2. Put the machines on different networks, for example the Air on a phone hotspot and the VM on home broadband. Repeat chat, Draw/Comment and an agent request from the guest.
3. Invite a third participant. All should see the same accepted source and conversation; only the host invokes OMP.
4. Close/reopen the owner's UI, then restart its background host. Check automatic reconnection with the original guest membership and no duplicated commands.
5. Test leaving, reused/expired invitations, wrong host identity and Stop sharing. Neither unrelated projects nor agent credentials should be disclosed.
6. Test the relay-only diagnostic mode below, and check CPU/memory and responsiveness on the Air.

Automated Iroh tests use real native helpers and real QUIC/TLS connections over loopback without internet discovery or public relays. They cover concurrent guests and windows sharing one endpoint, agent changes, LAN coexistence and upgrades, replayed invitations, certificate pins, reconnects and background-host survival. This does not substitute for the different-network physical acceptance test.

## Networking diagnostics for development

`CENTAUR_NETWORK` can override the bundled helper executable when developing. It is never taken from an invitation. The Unix control socket and endpoint identity are private to the OS user under `network/`; the key must not be copied into an invitation or project source. A damaged existing key fails closed rather than silently creating a different host identity.

- `CENTAUR_IROH_LOCAL=1` disables relays/discovery and binds only loopback; used by sandboxed CI integration tests.
- `CENTAUR_IROH_RELAY_ONLY=1` disables direct IP transports and forces relay transport, for testing fallback. Set this on both participants before starting their helpers. Close all local windows and stop their background hosts, wait 15 seconds for old helpers to exit, then launch with the variable set. The two diagnostic modes cannot be combined. Remove the variable and repeat the restart to return to automatic direct/relay operation.

Normal users need neither variable. Relay-only testing still requires internet access to the n0 services; it does not weaken TLS or endpoint identity verification.
