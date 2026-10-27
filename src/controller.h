#pragma once
#include "session.h"
#include <QObject>
#include <QVariantMap>
#include <QProcess>
#include <QSettings>
#include <QColor>

class Controller : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList projects READ projects NOTIFY changed)
    Q_PROPERTY(QVariantMap project READ project NOTIFY changed)
    Q_PROPERTY(QString projectId READ projectId NOTIFY changed)
    Q_PROPERTY(QString author READ author WRITE setAuthor NOTIFY changed)
    Q_PROPERTY(bool agentAvailable READ agentAvailable NOTIFY changed)
    Q_PROPERTY(QString agentModel READ agentModel NOTIFY changed)
    Q_PROPERTY(bool agentBusy READ agentBusy NOTIFY changed)
    Q_PROPERTY(QString previewStatus READ previewStatus NOTIFY previewChanged)
    Q_PROPERTY(bool previewRunning READ previewRunning NOTIFY previewChanged)
    Q_PROPERTY(bool embeddingSupported READ embeddingSupported CONSTANT)
    Q_PROPERTY(QString socketName READ socketName CONSTANT)
    Q_PROPERTY(int surfaceCount READ surfaceCount WRITE setSurfaceCount NOTIFY previewChanged)
    Q_PROPERTY(QString dataRoot READ dataRoot CONSTANT)
    Q_PROPERTY(bool gridEnabled READ gridEnabled WRITE setGridEnabled NOTIFY preferencesChanged)
    Q_PROPERTY(int gridSize READ gridSize WRITE setGridSize NOTIFY preferencesChanged)
    Q_PROPERTY(int gridOpacity READ gridOpacity WRITE setGridOpacity NOTIFY preferencesChanged)
    Q_PROPERTY(QColor gridColor READ gridColor WRITE setGridColor NOTIFY preferencesChanged)
    Q_PROPERTY(bool remoteProject READ remoteProject NOTIFY changed)
    Q_PROPERTY(bool canContribute READ canContribute NOTIFY changed)
    Q_PROPERTY(QString connectionStatus READ connectionStatus NOTIFY changed)
    Q_PROPERTY(QString localAddress READ localAddress CONSTANT)
    Q_PROPERTY(QString invitationCode READ invitationCode NOTIFY changed)
    Q_PROPERTY(QString joinStatus READ joinStatus NOTIFY changed)
    Q_PROPERTY(bool joining READ joining NOTIFY changed)
    Q_PROPERTY(QString agentExecutable READ agentExecutable NOTIFY changed)
public:
    explicit Controller(QString root, QObject *parent = nullptr);
    ~Controller() override;
    void start(bool background = false);
    void openStarterProject();
    QVariantList projects() const { return m_projects; }
    QVariantMap project() const { return m_states.value(m_projectId).toVariantMap(); }
    QString projectId() const { return m_projectId; }
    QString author() const;
    void setAuthor(const QString &author);
    bool agentAvailable() const;
    QString agentModel() const { return project().value("agentModel").toString(); }
    bool agentBusy() const;
    QString previewStatus() const { return m_previewStatus; }
    bool previewRunning() const { return m_preview.state() == QProcess::Running; }
    bool embeddingSupported() const;
    QString socketName() const;
    QString dataRoot() const { return m_session.root(); }
    bool gridEnabled() const { return m_gridEnabled; }
    int gridSize() const { return m_gridSize; }
    int gridOpacity() const { return m_gridOpacity; }
    QColor gridColor() const { return m_gridColor; }
    void setGridEnabled(bool value);
    void setGridSize(int value);
    void setGridOpacity(int value);
    void setGridColor(const QColor &value);
    QString agentExecutable() const { return m_agentExecutable; }
    bool remoteProject() const { return m_shared.contains(m_projectId); }
    bool canContribute() const;
    QString connectionStatus() const;
    QString localAddress() const { return CollaborationHost::suggestedAddress(); }
    QString invitationCode() const { return m_invitationCode; }
    QString joinStatus() const;
    bool joining() const { return !m_joiningId.isEmpty(); }
    Q_INVOKABLE void invitePeople(const QString &address);
    Q_INVOKABLE void stopSharing();
    Q_INVOKABLE void joinProject(const QString &code, const QString &name);
    Q_INVOKABLE void cancelJoin();
    Q_INVOKABLE void leaveProject(const QString &id);
    Q_INVOKABLE void copyInvitation();
    int surfaceCount() const { return m_surfaceCount; }
    void setSurfaceCount(int count);
    Q_INVOKABLE void createProject(const QString &name, const QString &description);
    Q_INVOKABLE void openProject(const QString &id);
    Q_INVOKABLE void closeProject();
    Q_INVOKABLE void archiveProject(const QString &id);
    Q_INVOKABLE void renameProject(const QString &id, const QString &name);
    Q_INVOKABLE void deleteProject(const QString &id);
    Q_INVOKABLE bool sendMessage(const QString &text, const QString &image = {}, int imageRevision = 0);
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
    Q_INVOKABLE void revealData();
signals:
    void joined();
    void preferencesChanged();
    void changed();
    void previewChanged();
    void previewStopping();
    void previewOutput(const QByteArray &output);
    void error(const QString &message);
private:
    void receive(const QJsonObject &data);
    void command(QJsonObject data);
    bool route(const QString &id, QJsonObject data);
    void refresh();
    void addShared(SharedProject *project);
    QString projectPath() const;
    QJsonObject m_localSnapshot;
    QHash<QString, SharedProject *> m_shared;
    QString m_invitationCode;
    QString m_joiningId;
    QString m_joinMessage;
    void savePreferences();
    QSettings m_preferences;
    Session m_session;
    QProcess m_preview;
    QVariantList m_projects;
    QHash<QString, QJsonObject> m_states;
    QString m_projectId;
    QString m_author;
    QString m_busyProject;
    QString m_previewStatus;
    QString m_agentExecutable;
    bool m_gridEnabled = false;
    int m_gridSize = 8;
    int m_gridOpacity = 50;
    QColor m_gridColor = QColor("#BAE6FF");
    bool m_agentAvailable = false;
    bool m_stopping = false;
    int m_surfaceCount = 0;
};
