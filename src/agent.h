#pragma once
#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QJsonObject>
#include <QElapsedTimer>
#include <QLocalSocket>
#include <QTemporaryDir>
#include <memory>

// Only host-authored fields may leave the validation boundary.
struct EditIssue {
    QString category, stage, hint;
    int operation = 0; // 1-based edit within the response, or 0 for the envelope.
    bool correctable = false;
};

// The agent proposes source; only the project coordinator can apply it.
class Agent : public QObject {
    Q_OBJECT
public:
    explicit Agent(QObject *parent = nullptr, int deadlineMs = 180000, QString designSocket = "/run/centaur-figma.sock");
    ~Agent() override;
    bool available() const;
    QString executable() const;
    bool busy() const;
    void ask(const QString &projectPath, const QJsonObject &state, const QString &source,
             const QString &imagePath = {}, const QString &runId = {});
    void cancel();
    void setModel(const QString &model) { m_selectedModel = model; }
    static QJsonObject parseReply(const QByteArray &text, QString *error, EditIssue *issue = nullptr);
    EditIssue validationIssue() const { return m_issue; }
    static QJsonObject prepareContext(QJsonObject state);
    static QJsonObject resolvePatch(const QJsonObject &patch, const QString &source, QString *error, EditIssue *issue = nullptr);
    QJsonObject diagnostics() const;
signals:
    void idle();
    void completed(const QJsonObject &reply);
    void failed(const QString &message);
    void modelReported(const QString &model);
    void progress(const QJsonObject &event);
    void resultReady(const QString &runId, const QJsonObject &reply);
    void failureReady(const QString &runId, const QString &message, const QJsonObject &details);
private:
    void prepareVisuals(const QString &project, QJsonObject state, const QString &source, const QString &canvas);
    void startPrepared(const QString &projectPath, const QJsonObject &state, const QString &source, const QStringList &images);
    void closeDesignSocket();
    QString m_designSocketPath;
    QLocalSocket *m_designSocket = nullptr;
    std::unique_ptr<QTemporaryDir> m_visualDir;
    void readOutput();
    void readLine(const QByteArray &line);
    void readMessage(const QJsonObject &message, bool complete);
    void observe(const QString &phase, bool force = false);
    void stopProcess();
    void failRun(const QString &code, const QString &message);
    EditIssue m_issue;
    QProcess m_process;
    QTimer m_timeout;
    bool m_cancelled = false;
    QString m_promptFile;
    QByteArray m_pendingOutput;
    QByteArray m_textOutput;
    QByteArray m_replyOutput;
    QByteArray m_responsePrefix;
    QString m_reportedModel;
    QString m_selectedModel, m_requestedModel;
    bool m_structuredOutput = false;
    QElapsedTimer m_clock;
    QString m_runId, m_phase, m_lastActivePhase, m_failureCode, m_lastEvent, m_providerOutcome;
    qint64 m_lastEventMs = -1, m_lastProviderMs = -1, m_lastPublishedMs = -1000;
    qint64 m_stdoutBytes = 0, m_stderrBytes = 0, m_promptBytes = 0;
    qint64 m_responseTextBytes = 0;
    int m_eventCount = 0, m_deltaCount = 0, m_retryCount = 0;
    int m_textUpdates = 0, m_thinkingUpdates = 0, m_turnCount = 0, m_nativeToolStarts = 0;
    int m_deadlineMs;
    qint64 m_processGroup = 0;
    bool m_started = false, m_agentEnded = false, m_resolving = false, m_streamIsPatch = false;
};
