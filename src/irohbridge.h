#pragma once
#include <QObject>
#include <QLocalSocket>
#include <QTimer>
#include <QElapsedTimer>
#include <QJsonObject>

// Private control channel to the single native helper for this data directory.
// App traffic stays inside the existing pinned TLS session over the tunnel.
class IrohBridge : public QObject {
    Q_OBJECT
public:
    explicit IrohBridge(const QString &root, QObject *parent = nullptr);
    ~IrohBridge() override;
    void listen(quint16 port);
    void unlisten();
    void refresh();
    void tunnel(const QJsonObject &remote);
    void disconnectTunnel();
    bool ready() const { return m_ready; }
    QJsonObject address() const { return m_address; }
signals:
    void prepared();
    void tunnelReady(quint16 port);
    void failed(const QString &message);
    void unavailable();
private:
    void start();
    void stop();
    void connectHelper();
    void read();
    void send(const QJsonObject &command);
    QString m_folder;
    QLocalSocket m_socket;
    QTimer m_retry;
    QElapsedTimer m_startup;
    QByteArray m_buffer;
    QJsonObject m_address;
    QJsonObject m_remote;
    quint16 m_port = 0;
    quint64 m_request = 0;
    bool m_ready = false;
    bool m_registered = false;
    bool m_spawned = false;
    bool m_started = false;
};
