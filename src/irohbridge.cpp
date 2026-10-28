#include "irohbridge.h"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QProcess>

IrohBridge::IrohBridge(const QString &root, QObject *parent) : QObject(parent), m_folder(root + "/network") {
    m_socket.setReadBufferSize(32769);
    m_retry.setSingleShot(true);
    connect(&m_retry, &QTimer::timeout, this, &IrohBridge::connectHelper);
    connect(&m_socket, &QLocalSocket::readyRead, this, &IrohBridge::read);
    connect(&m_socket, &QLocalSocket::connected, this, [this] { m_buffer.clear(); m_registered = false; });
    connect(&m_socket, &QLocalSocket::disconnected, this, [this] {
        m_ready = false; m_registered = false; m_spawned = false; m_startup.restart();
        emit unavailable();
        if (m_started) m_retry.start(1000);
    });
    connect(&m_socket, &QLocalSocket::errorOccurred, this, [this] {
        if (!m_started || m_socket.state() != QLocalSocket::UnconnectedState) return;
        if (!m_spawned) {
            m_spawned = true;
            QProcess helper;
            helper.setProgram(qEnvironmentVariable("CENTAUR_NETWORK", QCoreApplication::applicationDirPath() + "/centaur-network"));
            helper.setArguments({"--state-dir", m_folder});
            helper.setStandardOutputFile(QProcess::nullDevice()); helper.setStandardErrorFile(QProcess::nullDevice());
            if (!helper.startDetached()) { emit failed("Could not start Centaur’s native networking helper. Check this installation."); m_retry.start(5000); return; }
        }
        if (m_startup.elapsed() > 15000) {
            emit failed("Could not connect to Centaur’s networking helper. Check this installation and the data directory.");
            m_startup.restart(); m_spawned = false; m_retry.start(5000);
        } else m_retry.start(200);
    }, Qt::QueuedConnection);
}
IrohBridge::~IrohBridge() { m_started = false; disconnect(&m_socket, nullptr, this, nullptr); m_socket.abort(); }
void IrohBridge::start() {
    if (m_started) return;
    m_started = true; m_startup.start();
    if (!QDir().mkpath(m_folder)) { m_started = false; emit failed("Could not create the private networking directory."); return; }
    QFile::setPermissions(m_folder, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
    connectHelper();
}
void IrohBridge::stop() {
    m_started = false; m_ready = false; m_registered = false; m_spawned = false;
    m_retry.stop(); m_socket.abort(); m_buffer.clear();
}
void IrohBridge::connectHelper() { if (m_socket.state() == QLocalSocket::UnconnectedState) m_socket.connectToServer(m_folder + "/iroh.sock"); }
void IrohBridge::send(const QJsonObject &command) {
    if (m_socket.state() == QLocalSocket::ConnectedState) m_socket.write(QJsonDocument(command).toJson(QJsonDocument::Compact) + '\n');
}
void IrohBridge::listen(quint16 port) { m_port = port; m_registered = false; start(); if (m_ready) { m_registered = true; send({{"op", "listen"}, {"port", port}}); } }
void IrohBridge::unlisten() { m_port = 0; m_registered = false; send({{"op", "unlisten"}}); if (m_remote.isEmpty()) stop(); }
void IrohBridge::refresh() { start(); if (m_ready) send({{"op", "info"}}); }
void IrohBridge::tunnel(const QJsonObject &remote) {
    m_remote = remote; ++m_request; start();
    if (m_ready) send({{"op", "connect"}, {"request", double(m_request)}, {"node", remote["node"]}, {"relay", remote["relay"]}, {"addresses", remote["addresses"]}});
}
void IrohBridge::disconnectTunnel() { m_remote = {}; ++m_request; send({{"op", "disconnect"}}); if (!m_port) stop(); }
void IrohBridge::read() {
    m_buffer += m_socket.readAll();
    if (m_buffer.size() > 32768) { m_socket.abort(); return; }
    while (m_buffer.contains('\n')) {
        const auto n = m_buffer.indexOf('\n'); const auto data = QJsonDocument::fromJson(m_buffer.left(n)).object(); m_buffer.remove(0, n + 1);
        const auto event = data["event"].toString();
        if (event == "ready" && data["version"] == 1 && data["node"].toString().size() == 64) {
            m_address = {{"node", data["node"]}, {"relay", data["relay"]}, {"addresses", data["addresses"]}};
            if (m_port && !m_registered) { m_registered = true; send({{"op", "listen"}, {"port", m_port}}); continue; }
            const bool first = !m_ready; m_ready = true;
            if (first && !m_remote.isEmpty()) send({{"op", "connect"}, {"request", double(m_request)}, {"node", m_remote["node"]}, {"relay", m_remote["relay"]}, {"addresses", m_remote["addresses"]}});
            emit prepared();
        } else if (data["request"].toDouble() == double(m_request) && !m_remote.isEmpty()) {
            if (event == "tunnel" && data["port"].toInt() > 0 && data["port"].toInt() <= 65535) emit tunnelReady(quint16(data["port"].toInt()));
            else if (event == "error" || event == "closed") emit failed("Host unavailable · reconnecting through Iroh");
        }
    }
}
