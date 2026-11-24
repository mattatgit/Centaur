#pragma once
#include "workspace.h"
#include "irohbridge.h"
#include <QObject>
#include <QIODevice>
#include <QSslSocket>
#include <QTcpServer>
#include <QTimer>
#include <QLockFile>
#include <memory>
#include <QJsonObject>
#include <QJsonArray>
#include <QSet>
#include <functional>

class TlsServer : public QTcpServer {
public:
    using QTcpServer::QTcpServer;
    std::function<void(QSslSocket *)> accepted;
protected:
    void incomingConnection(qintptr descriptor) override;
};

// The TLS listener exposes only project-scoped, authenticated commands.
class CollaborationHost : public QObject {
    Q_OBJECT
public:
    explicit CollaborationHost(const QString &root, QObject *parent = nullptr);
    ~CollaborationHost() override;
    QString invite(const QString &id, const QString &owner, const QString &address, QString *error);
    void inviteInternet(const QString &id, const QString &owner, std::function<void(QString, QString)> reply);
    bool stopSharing(const QString &id, QString *error, bool projectRemoved = false);
    void publish(const QJsonObject &snapshot);
    QJsonObject sharing(const QString &id) const;
    bool setOwnerDisplayName(const QString &name);
    void refreshAvatar();
    static QString suggestedAddress();
    quint16 port() const { return m_server.serverPort(); }
    bool preparingInvitation() const { return !m_invitations.isEmpty(); }
    void setUpdating(bool value) { m_updating = value; }
signals:
    void command(const QJsonObject &command, QIODevice *sender);
    void membershipChanged();
private:
    bool listen(QString *error);
    bool certificate(QString *error);
    bool listenInternet(QString *error);
    bool save(QString *error);
    void restoreListeners();
    bool leave(const QString &id, const QString &hash);
    void removePeer(QSslSocket *socket, const QString &reason);
    void accept(QSslSocket *socket);
    void read(QSslSocket *socket);
    void receive(QSslSocket *socket, QJsonObject data);
    void sendSnapshot(QSslSocket *socket);
    void acknowledge(QSslSocket *socket, qint64 sequence);
    Workspace m_workspace;
    TlsServer m_server;
    TlsServer m_internetServer;
    IrohBridge m_iroh;
    struct Invitation { QString id, owner; std::function<void(QString, QString)> reply; };
    QHash<quint64, Invitation> m_invitations;
    quint64 m_invitationSerial = 0;
    QJsonObject m_shares;
    QJsonObject m_revocations;
    QString m_avatar;
    QJsonObject m_snapshot;
    struct Peer {
        QByteArray buffer;
        QString project, member, name;
        qint64 lastSeen = 0;
        QString credential;
        bool avatars = false;
        QSet<QString> sentAvatars;
    };
    QHash<QSslSocket *, Peer> m_peers;
    QTimer m_watchdog;
    bool m_updating = false;
};

class SharedProject : public QObject {
    Q_OBJECT
public:
    SharedProject(QString root, QJsonObject connection, QObject *parent = nullptr);
    ~SharedProject() override;
    static QJsonObject parseInvitation(const QString &code, QString *error);
    void start();
    void release();
    bool leave();
    void refreshAvatar();
    bool send(QJsonObject command);
    QString id() const { return m_connection["project"].toString(); }
    QString path() const { return m_root + "/shared/" + id(); }
    QString author() const { return m_connection["displayName"].toString(m_connection["name"].toString()); }
    void setDisplayName(const QString &name);
    QJsonArray ownMemberships() const { return m_ownMemberships; }
    QString participantId() const { return m_connection["memberId"].toString(); }
    bool writable() const { return m_connected && !leaving() && m_editLock && m_editLock->isLocked(); }
    bool agentAvailable() const { return m_snapshot["agentAvailable"].toBool(); }
    bool busy() const { return m_snapshot["busy"].toBool(); }
    int pendingCount() const { return m_outbox.size(); }
    bool connected() const { return m_connected; }
    QString joinErrorCode() const { return m_joinErrorCode; }
    bool failed() const { return m_terminal; }
    bool removed() const { return m_removed; }
    bool leaving() const { return m_connection["leaving"].toBool(); }
    bool ended() const { return m_connection.contains("ended"); }
    QJsonObject endNotice() const;
    QString status() const { return m_status; }
    QJsonObject state() const { return m_snapshot["state"].toObject(); }
    bool save(QString *error = nullptr);
signals:
    void changed();
    void error(const QString &message);
    void annotationRejected(const QString &id, const QString &message);
private:
    QString m_joinErrorCode = "connection";
    void fetchNextAttachment();
    QJsonObject m_attachmentRequest;
    QSet<QString> m_checkedAttachments;
    void connectHost();
    void read();
    void receive(const QJsonObject &data);
    void flush();
    void finish(const QString &reason);
    void status(const QString &text);
    std::unique_ptr<QLockFile> m_editLock;
    QString m_status;
    QString m_root;
    QJsonObject m_connection;
    QJsonObject m_snapshot;
    QJsonArray m_outbox;
    QSslSocket m_socket;
    std::unique_ptr<IrohBridge> m_iroh;
    bool m_tunnelling = false;
    bool m_avatarProtocol = false;
    bool m_nameProtocol = false;
    QJsonArray m_ownMemberships;
    QString m_advertisedAvatar;
    quint64 m_connectSerial = 0;
    QByteArray m_buffer;
    QTimer m_retry;
    QTimer m_heartbeat;
    bool m_inflight = false;
    bool m_connected = false;
    bool m_removed = false;
    bool m_terminal = false;
    int m_delay = 1000;
    qint64 m_lastReceived = 0;
};
