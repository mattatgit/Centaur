#pragma once
#include "workspace.h"
#include "agent.h"
#include "collaboration.h"
#include <QObject>
#include <QLocalServer>
#include <QLocalSocket>
#include <QJsonObject>
#include <QSet>
#include <QProcess>
#include <QLockFile>
#include <memory>

// One authoritative writer per data directory. Other native windows join over
// an OS-user-only local socket; project-scoped TLS peers join the same writer.
class Session : public QObject {
    Q_OBJECT
public:
    explicit Session(const QString &root, QObject *parent = nullptr, int agentDeadlineMs = 180000);
    ~Session() override;
    void start(bool background = false);
    bool connected() const { return m_host || m_client.state() == QLocalSocket::ConnectedState; }
    void send(QJsonObject command);
    bool isHost() const { return m_host; }
    bool updateBlocked() const;
    QString root() const { return m_workspace.root(); }
signals:
    void annotationRejected(const QString &id, const QString &message);
    void snapshot(const QJsonObject &data);
    void error(const QString &message);
    void sourceChanged(const QString &projectId);
    void connectionChanged();
private:
    void acceptConnection();
    void read(QLocalSocket *socket);
    void handle(const QJsonObject &command, QIODevice *sender = nullptr);
    void publish(const QString &id = {});
    void reply(QIODevice *socket, const QJsonObject &data);
    void addMessage(QJsonObject &state, const QString &author, const QString &text, const QString &kind = "human",
                    const QJsonObject &comment = {}, const QString &participant = {}, const QString &conflictId = {}, const QJsonArray &attachments = {}, const QString &clientId = {});
    bool persist(const QString &id, QJsonObject state);
    void finishAgent(const QJsonObject &reply);
    void agentError(const QString &message, const QString &code = {});
    void applyProposal(const QString &id, QJsonObject state);
    void nextRequest();
    void retryRequest(QJsonObject &state);
    void beginActivity(const QString &id, const QJsonObject &request);
    void advanceActivity(const QString &id, const QString &phase, const QJsonObject &details = {});
    void endActivity(const QString &id);
    void settleActivity(const QString &id);
    QByteArray appDigest(const QString &id) const;
    bool importCommand(const QJsonObject &command, QIODevice *sender);
    bool correctImportBranch(const QString &id, QJsonObject &state, const QString &text, const QString &author);
    void importJob(const QString &id, const QString &mode, QJsonObject payload = {});
    void importResult(const QString &id, const QString &mode, const QJsonObject &result, int epoch = -1,
                      const QString &attempt = {}, const QString &operationId = {});
    void importTool(const QString &id, QJsonObject state, const QJsonObject &reply, const QString &author);
    void queueImport(QJsonObject &state, const QString &text, const QString &author);
    QHash<QString, QProcess *> m_imports;
    QJsonObject m_activeRequest;
    QHash<QString,QJsonObject> m_activities;
    QHash<QString,QByteArray> m_activitySources;
    QString m_expectedAgentRun;
    QTimer m_reconnect;
    std::unique_ptr<CollaborationHost> m_network;
    QString m_socketName;
    Workspace m_workspace;
    QLocalServer m_server;
    QLocalSocket m_client;
    QSet<QLocalSocket *> m_peers;
    QHash<QLocalSocket *, QByteArray> m_buffers;
    Agent m_agent;
    QProcess m_validator;
    QString m_agentProject;
    QString m_agentAuthor;
    QString m_validatingProject;
    int m_agentEpoch = 0;
    int m_validatingEpoch = 0;
    bool m_host = false;
    bool m_starting = true;
    QString m_updateToken;
    bool m_updateStopping = false;
    std::unique_ptr<QLockFile> m_lock;
};
