#include "collaboration.h"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHostAddress>
#include <QImageReader>
#include <QBuffer>
#include <QJsonDocument>
#include <QNetworkInterface>
#include <QProcess>
#include <QRandomGenerator>
#include <QSslConfiguration>
#include <QSslKey>
#include <QUuid>
#include <QRegularExpression>
#include <QUrl>
#include <utility>

namespace {
constexpr int maxFrame = 8 * 1024 * 1024;
qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
QString digest(const QByteArray &bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex()); }
QString secret() {
    QByteArray bytes(32, Qt::Uninitialized);
    for (int i = 0; i < bytes.size(); i += 4) { const auto n = QRandomGenerator::system()->generate(); memcpy(bytes.data() + i, &n, 4); }
    return QString::fromLatin1(bytes.toBase64(QByteArray::Base64UrlEncoding | QByteArray::OmitTrailingEquals));
}
QJsonObject readObject(const QString &path) {
    QFile file(path); return file.open(QIODevice::ReadOnly) ? QJsonDocument::fromJson(file.readAll()).object() : QJsonObject();
}
bool privateFile(const QString &path, const QJsonObject &value, QString *error = nullptr) {
    if (!Workspace::writeFile(path, QJsonDocument(value).toJson(QJsonDocument::Compact), error)) return false;
    return QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner);
}
void write(QIODevice *socket, const QJsonObject &data) {
    const auto bytes = QJsonDocument(data).toJson(QJsonDocument::Compact) + '\n';
    // Bound memory when a slow client stops consuming snapshots.
    if (auto *tcp = qobject_cast<QAbstractSocket *>(socket)) {
        if (bytes.size() > maxFrame || tcp->bytesToWrite() > maxFrame) { tcp->abort(); return; }
    }
    socket->write(bytes);
}
}

void TlsServer::incomingConnection(qintptr descriptor) {
    auto *socket = new QSslSocket(this);
    socket->setReadBufferSize(maxFrame + 1);
    if (!socket->setSocketDescriptor(descriptor)) { socket->deleteLater(); return; }
    if (accepted) accepted(socket); else socket->deleteLater();
}

CollaborationHost::CollaborationHost(const QString &root, QObject *parent) : QObject(parent), m_workspace(root), m_iroh(root) {
    m_shares = readObject(root + "/network/shares.json");
    m_server.accepted = [this](QSslSocket *socket) { accept(socket); };
    m_internetServer.accepted = m_server.accepted;
    connect(&m_iroh, &IrohBridge::prepared, this, [this] {
        const auto pending = std::exchange(m_invitations, {});
        for (const auto &request : pending) {
            QString error; const auto code = invite(request.id, request.owner, "iroh", &error);
            request.reply(code, error);
        }
        emit membershipChanged();
    });
    connect(&m_iroh, &IrohBridge::failed, this, [this](const QString &error) {
        const auto pending = std::exchange(m_invitations, {});
        for (const auto &request : pending) request.reply({}, error);
        emit membershipChanged();
    });
    connect(&m_iroh, &IrohBridge::unavailable, this, &CollaborationHost::membershipChanged);
    bool lan = false, internet = false;
    for (const auto &value : m_shares) {
        const auto share = value.toObject();
        lan |= share["lan"].toBool(!share.contains("iroh")); internet |= share["iroh"].toBool();
    }
    QString error; if (lan) listen(&error); if (internet) listenInternet(&error);
    m_watchdog.setInterval(5000);
    connect(&m_watchdog, &QTimer::timeout, this, [this] {
        const auto sockets = m_peers.keys();
        for (auto *socket : sockets) {
            const auto peer = m_peers.value(socket);
            if (now() - peer.lastSeen > (peer.member.isEmpty() ? 10000 : 30000)) socket->abort();
        }
    });
    m_watchdog.start();
}
CollaborationHost::~CollaborationHost() {
    for (auto *socket : m_peers.keys()) { disconnect(socket, nullptr, this, nullptr); socket->abort(); }
}
bool CollaborationHost::save(QString *error) { return privateFile(m_workspace.root() + "/network/shares.json", m_shares, error); }
QString CollaborationHost::suggestedAddress() {
    for (const auto &interface : QNetworkInterface::allInterfaces()) {
        if (!(interface.flags() & QNetworkInterface::IsUp) || interface.flags() & QNetworkInterface::IsLoopBack) continue;
        for (const auto &entry : interface.addressEntries()) {
            const auto ip = entry.ip();
            if (ip.protocol() == QAbstractSocket::IPv4Protocol && !ip.isLoopback() && !ip.isLinkLocal()) return ip.toString();
        }
    }
    return {};
}
bool CollaborationHost::certificate(QString *error) {
    if (!QSslSocket::supportsSsl()) { if (error) *error = "TLS support is unavailable in this installation."; return false; }
    const auto folder = m_workspace.root() + "/network";
    if (!QDir().mkpath(folder)) return false;
    QFile::setPermissions(folder, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
    const auto cert = folder + "/certificate.pem", key = folder + "/key.pem";
    if (!QFileInfo::exists(cert) || !QFileInfo::exists(key)) {
        QProcess openssl;
        openssl.start("openssl", {"req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "3650",
            "-subj", "/CN=Centaur local project host", "-keyout", key, "-out", cert});
        if (!openssl.waitForFinished(15000) || openssl.exitCode() != 0) {
            if (error) *error = "Could not create the host certificate. Check the OpenSSL installation.";
            return false;
        }
        QFile::setPermissions(key, QFile::ReadOwner | QFile::WriteOwner);
    }
    return true;
}
bool CollaborationHost::listen(QString *error) {
    if (m_server.isListening()) return true;
    if (!certificate(error)) return false;
    if (!m_server.listen(QHostAddress::AnyIPv4, quint16(qEnvironmentVariableIsSet("CENTAUR_PORT") ? qEnvironmentVariableIntValue("CENTAUR_PORT") : 43177))) {
        if (error) *error = "Could not start sharing on port 43177: " + m_server.errorString();
        return false;
    }
    return true;
}
bool CollaborationHost::listenInternet(QString *error) {
    if (!m_internetServer.isListening()) {
        if (!certificate(error)) return false;
        if (!m_internetServer.listen(QHostAddress::LocalHost, 0)) {
            if (error) *error = "Could not start the local project listener.";
            return false;
        }
        m_iroh.listen(m_internetServer.serverPort());
    }
    return true;
}
void CollaborationHost::inviteInternet(const QString &id, const QString &owner, std::function<void(QString, QString)> reply) {
    QString error;
    if (m_workspace.load(id).isEmpty()) { reply({}, "This project is unavailable."); return; }
    if (m_invitations.size() >= 8) { reply({}, "Wait for the current invitations to finish."); return; }
    if (!listenInternet(&error)) { reply({}, error); return; }
    const auto serial = ++m_invitationSerial;
    m_invitations.insert(serial, {id, owner, std::move(reply)});
    QTimer::singleShot(20000, this, [this, serial] {
        if (!m_invitations.contains(serial)) return;
        const auto request = m_invitations.take(serial);
        request.reply({}, "The networking helper is not ready. Check the installation and try again.");
    });
    m_iroh.refresh();
}
QString CollaborationHost::invite(const QString &id, const QString &owner, const QString &address, QString *error) {
    const bool internet = address == "iroh";
    const QHostAddress ip(address.trimmed());
    if (m_workspace.load(id).isEmpty() || (!internet && (ip.isNull() || ip == QHostAddress::AnyIPv4 || ip.protocol() != QAbstractSocket::IPv4Protocol))) {
        if (error) *error = "Choose this computer's reachable local IPv4 address.";
        return {};
    }
    if (internet ? !m_iroh.ready() : !listen(error)) return {};
    auto share = m_shares[id].toObject();
    if (!share.isEmpty() && !share.contains("iroh") && !share.contains("lan")) share["lan"] = true;
    share["owner"] = owner;
    share[internet ? "iroh" : "lan"] = true;
    auto invites = share["invites"].toObject();
    for (const auto &hash : invites.keys()) if (invites[hash].toDouble() < now()) invites.remove(hash);
    const auto token = secret();
    invites[digest(token.toUtf8())] = double(now() + 20 * 60 * 1000);
    share["invites"] = invites;
    m_shares[id] = share;
    if (!save(error)) return {};
    QFile certificate(m_workspace.root() + "/network/certificate.pem");
    if (!certificate.open(QIODevice::ReadOnly)) { if (error) *error = "Could not read the host certificate."; return {}; }
    const QSslCertificate cert(certificate.readAll());
    QJsonObject invitation{{"version", 1}, {"host", address.trimmed()}, {"port", m_server.serverPort()},
        {"project", id}, {"pin", QString::fromLatin1(cert.digest(QCryptographicHash::Sha256).toHex())}, {"invite", token}};
    if (internet) {
        invitation.remove("host"); invitation.remove("port");
        invitation["version"] = 2; invitation["transport"] = "iroh";
        invitation["endpoint"] = m_iroh.address();
    }
    return (internet ? "centaur2:" : "centaur1:") + QString::fromLatin1(QJsonDocument(invitation).toJson(QJsonDocument::Compact).toBase64(QByteArray::Base64UrlEncoding | QByteArray::OmitTrailingEquals));
}
QJsonObject CollaborationHost::sharing(const QString &id) const {
    const auto share = m_shares[id].toObject();
    QJsonArray names;
    for (const auto &value : share["members"].toObject()) names.append(value.toObject()["name"]);
    return {{"enabled", !share.isEmpty() && (m_server.isListening() || m_internetServer.isListening())}, {"internetReady", m_iroh.ready()}, {"members", names}};
}
bool CollaborationHost::stopSharing(const QString &id, QString *error) {
    for (const auto serial : m_invitations.keys()) if (m_invitations[serial].id == id) {
        const auto pending = m_invitations.take(serial); pending.reply({}, "Sharing was stopped before the invitation was created.");
    }
    const auto previous = m_shares;
    m_shares.remove(id);
    if (!save(error)) { m_shares = previous; return false; }
    for (auto *socket : m_peers.keys()) if (m_peers.value(socket).project == id) {
        write(socket, {{"type", "removed"}, {"message", "The owner stopped sharing this project."}});
        socket->disconnectFromHost();
    }
    bool internet = false, lan = false;
    for (const auto &value : m_shares) {
        const auto share = value.toObject(); internet |= share["iroh"].toBool();
        lan |= share["lan"].toBool(!share.contains("iroh"));
    }
    if (!lan) m_server.close();
    if (!internet) { m_iroh.unlisten(); m_internetServer.close(); }
    return true;
}
void CollaborationHost::accept(QSslSocket *socket) {
    if (m_peers.size() >= 24) { socket->abort(); socket->deleteLater(); return; }
    m_peers.insert(socket, {{}, {}, {}, {}, now()});
    const auto folder = m_workspace.root() + "/network/";
    socket->setLocalCertificate(folder + "certificate.pem");
    socket->setPrivateKey(folder + "key.pem");
    socket->setProtocol(QSsl::TlsV1_2OrLater);
    socket->setPeerVerifyMode(QSslSocket::VerifyNone); // Members authenticate inside TLS, not with client certificates.
    connect(socket, &QSslSocket::readyRead, this, [this, socket] { read(socket); });
    connect(socket, &QSslSocket::disconnected, this, [this, socket] { m_peers.remove(socket); socket->deleteLater(); });
    connect(socket, &QSslSocket::errorOccurred, this, [socket] { socket->abort(); });
    socket->startServerEncryption();
}
void CollaborationHost::read(QSslSocket *socket) {
    if (!socket->isEncrypted() || !m_peers.contains(socket)) return;
    m_peers[socket].buffer += socket->readAll();
    while (m_peers.contains(socket) && m_peers[socket].buffer.contains('\n')) {
        auto &buffer = m_peers[socket].buffer;
        const auto index = buffer.indexOf('\n');
        if (index > maxFrame) { socket->abort(); return; }
        QJsonParseError error;
        const auto data = QJsonDocument::fromJson(buffer.left(index), &error);
        buffer.remove(0, index + 1);
        if (error.error != QJsonParseError::NoError || !data.isObject()) { socket->abort(); return; }
        receive(socket, data.object());
    }
    if (m_peers.contains(socket) && m_peers[socket].buffer.size() > maxFrame) socket->abort();
}
void CollaborationHost::receive(QSslSocket *socket, QJsonObject data) {
    auto peer = m_peers.value(socket);
    peer.lastSeen = now(); m_peers[socket] = peer;
    auto reject = [socket](const QString &message) { write(socket, {{"type", "rejected"}, {"message", message}}); socket->disconnectFromHost(); };
    if (peer.member.isEmpty()) {
        if (data["type"] != "hello" || data["version"] != 1) { reject("This Centaur connection is incompatible."); return; }
        const auto id = data["project"].toString();
        auto share = m_shares[id].toObject();
        if (share.isEmpty() || m_workspace.load(id).isEmpty()) { reject("This project is no longer shared."); return; }
        const auto token = data["memberToken"].toString();
        if (token.size() != 43) { reject("The participant credential is invalid."); return; }
        const auto hash = digest(token.toUtf8());
        auto members = share["members"].toObject();
        auto member = members[hash].toObject();
        if (member.isEmpty()) {
            auto invites = share["invites"].toObject();
            const auto invitationHash = digest(data["invite"].toString().toUtf8());
            if (invites[invitationHash].toDouble() < now()) { reject("This invitation has expired or has already been used. Ask for a new one."); return; }
            auto name = data["name"].toString().trimmed().left(50);
            if (name.isEmpty()) { reject("Enter your name to join."); return; }
            QSet<QString> names{share["owner"].toString().toCaseFolded()};
            for (const auto &value : members) names.insert(value.toObject()["name"].toString().toCaseFolded());
            const auto state = m_workspace.load(id);
            for (const auto &value : state["messages"].toArray()) if (value.toObject()["kind"] == "human") names.insert(value.toObject()["author"].toString().toCaseFolded());
            for (const auto &value : state["contributors"].toArray()) names.insert(value.toString().toCaseFolded());
            for (const auto &value : state["annotations"].toArray()) names.insert(value.toObject()["author"].toString().toCaseFolded());
            for (const auto &value : state["decisions"].toArray()) for (const auto &author : value.toObject()["authors"].toArray()) names.insert(author.toString().toCaseFolded());
            const auto original = name;
            int suffix = 2;
            while (names.contains(name.toCaseFolded())) name = original.left(40) + " (" + QString::number(suffix++) + ")";
            member = {{"id", QUuid::createUuid().toString(QUuid::WithoutBraces)}, {"name", name}};
            members[hash] = member; share["members"] = members;
            invites.remove(invitationHash); share["invites"] = invites;
            m_shares[id] = share;
            QString error;
            if (!save(&error)) { reject("Could not save your membership. Ask the owner to check storage."); return; }
        }
        peer.project = id; peer.member = member["id"].toString(); peer.name = member["name"].toString(); m_peers[socket] = peer;
        write(socket, {{"type", "welcome"}, {"version", 1}, {"memberId", peer.member}, {"name", peer.name}});
        emit membershipChanged();
        sendSnapshot(socket);
        return;
    }
    if (data["type"] == "ping") { write(socket, {{"type", "pong"}}); return; }
    const auto sequence = qint64(data["sequence"].toDouble());
    auto state = m_workspace.load(peer.project);
    if (state.isEmpty()) { reject("This project is unavailable."); return; }
    const auto last = qint64(state["networkAcks"].toObject()[peer.member].toDouble());
    if (sequence <= 0 || sequence > last + 1) { reject("The connection needs to synchronise again."); return; }
    if (sequence <= last) { sendSnapshot(socket); write(socket, {{"type", "ack"}, {"sequence", double(sequence)}}); return; }
    const auto type = data["type"].toString();
    const QSet<QString> allowed{"message", "annotation", "undo", "accept", "cancel"};
    if (!allowed.contains(type) || data["projectId"].toString() != peer.project) {
        write(socket, {{"type", "error"}, {"message", "Only the owner can manage this project or its invitations."}});
        acknowledge(socket, sequence); return;
    }
    if ((type == "annotation" || type == "undo" || type == "accept") && data["baseRevision"] != state["revision"]) {
        write(socket, {{"type", "error"}, {"message", "The app changed before that action arrived. Please try it on the current app."}});
        acknowledge(socket, sequence); sendSnapshot(socket); return;
    }
    data["projectId"] = peer.project; data["author"] = peer.name; data["_memberId"] = peer.member;
    data.remove("image");
    if (type == "message" && !data["imageData"].toString().isEmpty()) {
        const auto bytes = QByteArray::fromBase64(data["imageData"].toString().toLatin1());
        QBuffer buffer; buffer.setData(bytes); buffer.open(QIODevice::ReadOnly);
        QImageReader image(&buffer, "png"); const auto size = image.size();
        if (bytes.size() <= 2 * 1024 * 1024 && size.isValid() && size.width() <= 4096 && size.height() <= 4096) {
            const auto path = m_workspace.projectPath(peer.project) + "/.centaur/remote-" + QUuid::createUuid().toString(QUuid::WithoutBraces) + ".png";
            if (Workspace::writeFile(path, bytes)) data["image"] = path;
        }
    }
    data.remove("imageData");
    emit command(data, socket);
    acknowledge(socket, sequence);
}
void CollaborationHost::acknowledge(QSslSocket *socket, qint64 sequence) {
    const auto peer = m_peers.value(socket);
    auto state = m_workspace.load(peer.project);
    auto acks = state["networkAcks"].toObject();
    if (qint64(acks[peer.member].toDouble()) < sequence) {
        acks[peer.member] = double(sequence); state["networkAcks"] = acks;
        QString error;
        if (!m_workspace.save(peer.project, state, &error)) { socket->abort(); return; }
    }
    write(socket, {{"type", "ack"}, {"sequence", double(sequence)}});
}
void CollaborationHost::publish(const QJsonObject &snapshot) {
    m_snapshot = snapshot;
    for (auto *socket : m_peers.keys()) if (!m_peers.value(socket).member.isEmpty()) sendSnapshot(socket);
}
void CollaborationHost::sendSnapshot(QSslSocket *socket) {
    const auto peer = m_peers.value(socket);
    auto state = m_workspace.load(peer.project);
    if (state.isEmpty() || state["archived"].toBool()) {
        write(socket, {{"type", "removed"}, {"message", "The owner removed this project."}}); socket->disconnectFromHost(); return;
    }
    const auto source = m_workspace.source(peer.project);
    state["queueCount"] = state["agentQueue"].toArray().size();
    state.remove("networkAcks"); state.remove("agentQueue"); state.remove("activeRequest");
    auto messages = state["messages"].toArray();
    int size = QJsonDocument(messages).toJson(QJsonDocument::Compact).size();
    while (messages.size() > 1 && size > 2 * 1024 * 1024) {
        size -= QJsonDocument(messages.first().toObject()).toJson(QJsonDocument::Compact).size(); messages.removeFirst();
    }
    state["messages"] = messages;
    auto decisions = state["decisions"].toArray();
    while (decisions.size() > 20) decisions.removeFirst();
    for (int i = 0; i < decisions.size(); ++i) { auto decision = decisions[i].toObject(); decision["summary"] = decision["summary"].toString().left(2000); decisions[i] = decision; }
    state["decisions"] = decisions;
    auto proposal = state["proposal"].toObject(); proposal.remove("qml"); state["proposal"] = proposal;
    write(socket, {{"type", "project"}, {"version", 1}, {"state", state}, {"source", source},
        {"sourceHash", digest(source.toUtf8())}, {"busy", m_snapshot["busyProject"] == peer.project}, {"agentAvailable", m_snapshot["agentAvailable"]}});
}

SharedProject::SharedProject(QString root, QJsonObject connection, QObject *parent) : QObject(parent), m_root(std::move(root)), m_connection(std::move(connection)) {
    QDir().mkpath(path());
    QFile::setPermissions(m_root + "/shared", QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
    QFile::setPermissions(path(), QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
    m_editLock = std::make_unique<QLockFile>(path() + "/client.lock");
    if (m_editLock->tryLock(0)) m_outbox = m_connection["outbox"].toArray();
    m_snapshot = readObject(path() + "/snapshot.json");
    if (!m_snapshot.isEmpty()) Workspace::writeFile(path() + "/App.qml", m_snapshot["source"].toString().toUtf8());
    if (m_connection["transport"] == "iroh") {
        m_iroh = std::make_unique<IrohBridge>(m_root);
        connect(m_iroh.get(), &IrohBridge::tunnelReady, this, [this](quint16 port) {
            if (!m_tunnelling || m_terminal) return;
            m_tunnelling = false;
            m_socket.connectToHostEncrypted("127.0.0.1", port);
        });
        auto unavailable = [this] {
            m_tunnelling = false; m_socket.abort(); m_connected = false; m_inflight = false;
            if (!m_terminal) { status("Host unavailable · reconnecting through Iroh"); m_retry.start(m_delay); m_delay = qMin(15000, m_delay * 2); }
        };
        connect(m_iroh.get(), &IrohBridge::unavailable, this, unavailable);
        connect(m_iroh.get(), &IrohBridge::failed, this, [unavailable](const QString &) { unavailable(); });
    }
    m_retry.setSingleShot(true);
    connect(&m_retry, &QTimer::timeout, this, &SharedProject::connectHost);
    m_socket.setReadBufferSize(maxFrame + 1);
    m_socket.setProtocol(QSsl::TlsV1_2OrLater);
    // The invitation pins the host certificate. No credential is sent before
    // encrypted() verifies the exact SHA-256 pin; public CAs are not involved.
    m_socket.setPeerVerifyMode(QSslSocket::VerifyNone);
    connect(&m_socket, &QSslSocket::encrypted, this, [this] {
        const auto pin = QString::fromLatin1(m_socket.peerCertificate().digest(QCryptographicHash::Sha256).toHex());
        if (pin != m_connection["pin"].toString()) { m_terminal = true; status("Host identity changed · ask for a new invitation"); emit error(m_status); m_socket.abort(); if (m_iroh) m_iroh->disconnectTunnel(); return; }
        write(&m_socket, {{"type", "hello"}, {"version", 1}, {"project", id()}, {"memberToken", m_connection["memberToken"]}, {"invite", m_connection["invite"]}, {"name", author()}});
    });
    connect(&m_socket, &QSslSocket::readyRead, this, &SharedProject::read);
    connect(&m_socket, &QSslSocket::disconnected, this, [this] {
        m_connected = false; m_inflight = false; m_heartbeat.stop();
        if (!m_terminal) { status("Host unavailable · reconnecting"); m_retry.start(m_delay); m_delay = qMin(15000, m_delay * 2); }
        else emit changed();
    });
    connect(&m_socket, &QSslSocket::errorOccurred, this, [this] {
        if (m_socket.state() == QAbstractSocket::UnconnectedState && !m_terminal) { m_connected = false; m_inflight = false; status("Host unavailable · reconnecting"); m_retry.start(m_delay); m_delay = qMin(15000, m_delay * 2); }
    });
    m_heartbeat.setInterval(5000);
    connect(&m_heartbeat, &QTimer::timeout, this, [this] {
        if (!m_editLock->isLocked() && m_editLock->tryLock(0)) {
            const auto saved = readObject(path() + "/connection.json");
            if (saved["memberToken"] != m_connection["memberToken"]) {
                m_terminal = true; m_removed = true; m_connected = false;
                status("This device left the project"); m_socket.abort(); return;
            }
            m_connection = saved; m_outbox = saved["outbox"].toArray(); m_inflight = false;
            status("Connected · shared project"); flush();
        }
        if (now() - m_lastReceived > 20000) m_socket.abort(); else write(&m_socket, {{"type", "ping"}});
    });
}
SharedProject::~SharedProject() { disconnect(&m_socket, nullptr, this, nullptr); m_socket.abort(); }
QJsonObject SharedProject::parseInvitation(const QString &code, QString *error) {
    const auto text = code.trimmed();
    const bool internet = text.startsWith("centaur2:");
    auto data = (text.startsWith("centaur1:") || internet) && text.size() < 4096 ? QJsonDocument::fromJson(QByteArray::fromBase64(text.mid(9).toLatin1(), QByteArray::Base64UrlEncoding)).object() : QJsonObject();
    const auto id = data["project"].toString();
    const auto pin = data["pin"].toString();
    const auto ip = QHostAddress(data["host"].toString());
    const QRegularExpression hex("^[0-9a-f]{64}$"), token("^[A-Za-z0-9_-]{43}$");
    const auto endpoint = data["endpoint"].toObject();
    bool validEndpoint = hex.match(endpoint["node"].toString()).hasMatch() && endpoint["addresses"].isArray() && endpoint["addresses"].toArray().size() <= 16;
    const auto relay = endpoint["relay"].toString(); const QUrl relayUrl(relay);
    validEndpoint &= relay.isEmpty() || (relay.size() <= 256 && relayUrl.isValid() && relayUrl.scheme() == "https" && !relayUrl.host().isEmpty() && relayUrl.userInfo().isEmpty() && !relayUrl.hasQuery() && !relayUrl.hasFragment());
    for (const auto &value : endpoint["addresses"].toArray()) {
        const QUrl url("tcp://" + value.toString()); const QHostAddress direct(url.host());
        validEndpoint &= value.isString() && value.toString().size() < 128 && !direct.isNull() && !direct.isMulticast() && direct != QHostAddress::AnyIPv4 && direct != QHostAddress::AnyIPv6 && url.port() > 0 && url.port() <= 65535 && url.path().isEmpty() && url.userInfo().isEmpty() && !url.hasQuery() && !url.hasFragment();
    }
    if (id.size() != 36 || QUuid(id).isNull() || !hex.match(pin).hasMatch() || !token.match(data["invite"].toString()).hasMatch()
        || (internet ? data["version"] != 2 || data["transport"] != "iroh" || !validEndpoint
                     : data["version"] != 1 || ip.isNull() || ip.protocol() != QAbstractSocket::IPv4Protocol || data["port"].toInt() < 1 || data["port"].toInt() > 65535)) {
        if (error) *error = "That invitation is not valid. Paste the complete code from the project owner.";
        return {};
    }
    // Never accept arbitrary fields or filesystem paths from an invitation.
    QJsonObject result{{"project", id}, {"pin", pin}, {"invite", data["invite"]}, {"memberToken", secret()}};
    if (internet) {
        result["transport"] = "iroh";
        result["endpoint"] = QJsonObject{{"node", endpoint["node"]}, {"relay", relay.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(relay)}, {"addresses", endpoint["addresses"]}};
    } else { result["host"] = ip.toString(); result["port"] = data["port"]; }
    return result;
}
bool SharedProject::save(QString *error) {
    if (m_editLock && !m_editLock->isLocked()) return true; // Another window owns this device’s outgoing queue.
    if (!QDir().mkpath(path())) return false;
    QFile::setPermissions(m_root + "/shared", QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
    QFile::setPermissions(path(), QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
    m_connection["outbox"] = m_outbox;
    return privateFile(path() + "/connection.json", m_connection, error);
}
void SharedProject::release() {
    m_terminal = true; m_connected = false; m_retry.stop(); m_heartbeat.stop();
    if (m_iroh) m_iroh->disconnectTunnel();
    disconnect(&m_socket, nullptr, this, nullptr); m_socket.abort(); m_editLock.reset();
}
void SharedProject::start() { if (!m_terminal) connectHost(); }
void SharedProject::status(const QString &text) { m_status = text; emit changed(); }
void SharedProject::connectHost() {
    if (m_terminal || m_tunnelling || m_socket.state() != QAbstractSocket::UnconnectedState) return;
    m_buffer.clear(); m_connected = false; status("Connecting to project host…");
    if (m_iroh) { m_tunnelling = true; m_iroh->tunnel(m_connection["endpoint"].toObject()); }
    else m_socket.connectToHostEncrypted(m_connection["host"].toString(), quint16(m_connection["port"].toInt()));
    const auto attempt = ++m_connectSerial;
    QTimer::singleShot(m_iroh ? 45000 : 10000, this, [this, attempt] { if (attempt == m_connectSerial && !m_connected && m_socket.state() != QAbstractSocket::UnconnectedState) m_socket.abort(); });
}
void SharedProject::read() {
    m_buffer += m_socket.readAll();
    while (m_buffer.contains('\n')) {
        const auto index = m_buffer.indexOf('\n');
        if (index > maxFrame) { m_socket.abort(); return; }
        QJsonParseError error;
        const auto doc = QJsonDocument::fromJson(m_buffer.left(index), &error); m_buffer.remove(0, index + 1);
        if (error.error != QJsonParseError::NoError || !doc.isObject()) { m_socket.abort(); return; }
        m_lastReceived = now(); receive(doc.object());
    }
    if (m_buffer.size() > maxFrame) m_socket.abort();
}
void SharedProject::receive(const QJsonObject &data) {
    const auto type = data["type"].toString();
    if (type == "welcome") {
        m_connection["name"] = data["name"]; m_connection["memberId"] = data["memberId"]; m_connection.remove("invite");
        if (!save()) { m_terminal = true; emit error("Could not save your project membership."); m_socket.abort(); }
        emit changed();
    } else if (type == "project") {
        const auto state = data["state"].toObject(); const auto source = data["source"].toString();
        if (state["id"] != id() || source.size() > 256000 || source.trimmed().isEmpty() || digest(source.toUtf8()) != data["sourceHash"].toString()) { m_socket.abort(); return; }
        if (!privateFile(path() + "/snapshot.json", data) || !Workspace::writeFile(path() + "/App.qml", source.toUtf8())) {
            emit error("Could not save the shared app on this device."); m_socket.abort(); return;
        }
        m_snapshot = data; m_connected = true; m_delay = 1000;
        status(writable() ? "Connected · shared project" : "Open in another window · view only"); m_heartbeat.start(); flush();
    } else if (type == "ack") {
        if (!m_outbox.isEmpty() && m_outbox.first().toObject()["sequence"] == data["sequence"]) { m_outbox.removeFirst(); m_inflight = false; if (save()) flush(); }
    } else if (type == "error") emit error(data["message"].toString());
    else if (type == "rejected" || type == "removed") {
        m_terminal = true; m_connected = false; m_removed = type == "removed";
        status(data["message"].toString()); emit error(m_status);
        // Keep cached source for recovery, but revoke the saved credential.
        QFile::remove(path() + "/connection.json"); m_socket.disconnectFromHost(); if (m_iroh) m_iroh->disconnectTunnel();
    }
}
bool SharedProject::send(QJsonObject command) {
    if (!writable()) { emit error("Use the connected editing window to send. Your draft stays here."); return false; }
    if (m_outbox.size() >= 100) { emit error("Wait for your pending actions to synchronise."); return false; }
    if (command["type"] == "message" && !command["image"].toString().isEmpty()) {
        QFile image(command["image"].toString());
        if (image.open(QIODevice::ReadOnly) && image.size() <= 2 * 1024 * 1024) command["imageData"] = QString::fromLatin1(image.readAll().toBase64());
    }
    command.remove("image"); command.remove("author");
    command["projectId"] = id(); command["baseRevision"] = state()["revision"];
    const auto sequence = qint64(m_connection["sequence"].toDouble()) + 1;
    command["sequence"] = double(sequence); m_connection["sequence"] = double(sequence);
    m_outbox.append(command);
    if (!save()) { m_outbox.removeLast(); m_connection["sequence"] = double(sequence - 1); emit error("Could not save your pending action. Please try again."); return false; }
    if (m_outbox.size() == 1) flush();
    return true;
}
void SharedProject::flush() { if (writable() && !m_inflight && !m_outbox.isEmpty()) { m_inflight = true; write(&m_socket, m_outbox.first().toObject()); } }
