#pragma once
#include "session.h"
#include <QObject>
#include <QVariantMap>
#include <QProcess>

class Controller : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList projects READ projects NOTIFY changed)
    Q_PROPERTY(QVariantMap project READ project NOTIFY changed)
    Q_PROPERTY(QString projectId READ projectId NOTIFY changed)
    Q_PROPERTY(QString author READ author WRITE setAuthor NOTIFY changed)
    Q_PROPERTY(bool agentAvailable READ agentAvailable NOTIFY changed)
    Q_PROPERTY(bool agentBusy READ agentBusy NOTIFY changed)
    Q_PROPERTY(QString previewStatus READ previewStatus NOTIFY previewChanged)
    Q_PROPERTY(bool previewRunning READ previewRunning NOTIFY previewChanged)
    Q_PROPERTY(bool embeddingSupported READ embeddingSupported CONSTANT)
    Q_PROPERTY(QString socketName READ socketName CONSTANT)
    Q_PROPERTY(int surfaceCount READ surfaceCount WRITE setSurfaceCount NOTIFY previewChanged)
    Q_PROPERTY(QString dataRoot READ dataRoot CONSTANT)
public:
    explicit Controller(QString root, QObject *parent = nullptr);
    ~Controller() override;
    void start();
    QVariantList projects() const { return m_projects; }
    QVariantMap project() const { return m_states.value(m_projectId).toVariantMap(); }
    QString projectId() const { return m_projectId; }
    QString author() const { return m_author; }
    void setAuthor(const QString &author);
    bool agentAvailable() const { return m_agentAvailable; }
    bool agentBusy() const { return !m_busyProject.isEmpty(); }
    QString previewStatus() const { return m_previewStatus; }
    bool previewRunning() const { return m_preview.state() == QProcess::Running; }
    bool embeddingSupported() const;
    QString socketName() const;
    QString dataRoot() const { return m_session.root(); }
    int surfaceCount() const { return m_surfaceCount; }
    void setSurfaceCount(int count);
    Q_INVOKABLE void createProject(const QString &name, const QString &description);
    Q_INVOKABLE void openProject(const QString &id);
    Q_INVOKABLE void closeProject();
    Q_INVOKABLE void archiveProject(const QString &id);
    Q_INVOKABLE void sendMessage(const QString &text, const QString &image = {}, int imageRevision = 0);
    Q_INVOKABLE void addAnnotation(const QVariantMap &annotation);
    Q_INVOKABLE void undoAnnotation();
    Q_INVOKABLE void acceptProposal();
    Q_INVOKABLE void renameAgent(const QString &name);
    Q_INVOKABLE void cancelAgent();
    Q_INVOKABLE void startPreview();
    Q_INVOKABLE void stopPreview();
    Q_INVOKABLE void restartPreview();
    Q_INVOKABLE QString capturePath() const;
    Q_INVOKABLE void revealProject();
signals:
    void changed();
    void previewChanged();
    void previewOutput(const QByteArray &output);
    void error(const QString &message);
private:
    void receive(const QJsonObject &data);
    void command(QJsonObject data);
    Session m_session;
    QProcess m_preview;
    QVariantList m_projects;
    QHash<QString, QJsonObject> m_states;
    QString m_projectId;
    QString m_author;
    QString m_busyProject;
    QString m_previewStatus;
    bool m_agentAvailable = false;
    bool m_stopping = false;
    int m_surfaceCount = 0;
};
