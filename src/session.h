#pragma once
#include "workspace.h"
#include "agent.h"
#include <QObject>
#include <QLocalServer>
#include <QLocalSocket>
#include <QJsonObject>
#include <QSet>
#include <QProcess>
#include <QLockFile>
#include <memory>

// One authoritative writer per data directory. Other native windows join over
// an OS-user-only local socket. Remote family collaboration is a later step.
class Session : public QObject {
    Q_OBJECT
public:
    explicit Session(const QString &root, QObject *parent = nullptr);
    ~Session() override;
    void start();
    void send(QJsonObject command);
    bool isHost() const { return m_host; }
    QString root() const { return m_workspace.root(); }
signals:
    void snapshot(const QJsonObject &data);
    void error(const QString &message);
    void sourceChanged(const QString &projectId);
private:
    void acceptConnection();
    void read(QLocalSocket *socket);
    void handle(const QJsonObject &command, QLocalSocket *sender = nullptr);
    void publish(const QString &id = {});
    void reply(QLocalSocket *socket, const QJsonObject &data);
    void addMessage(QJsonObject &state, const QString &author, const QString &text, const QString &kind = "human");
    bool persist(const QString &id, QJsonObject state);
    void finishAgent(const QJsonObject &reply);
    void agentError(const QString &message);
    void applyProposal(const QString &id, QJsonObject state);
    QString m_socketName;
    Workspace m_workspace;
    QLocalServer m_server;
    QLocalSocket m_client;
    QSet<QLocalSocket *> m_peers;
    QHash<QLocalSocket *, QByteArray> m_buffers;
    Agent m_agent;
    QProcess m_validator;
    QString m_agentProject;
    QString m_validatingProject;
    int m_agentEpoch = 0;
    int m_validatingEpoch = 0;
    bool m_host = false;
    bool m_starting = true;
    std::unique_ptr<QLockFile> m_lock;
};
