#pragma once
#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QJsonObject>
#include <QElapsedTimer>

// The agent proposes source; only the project coordinator can apply it.
class Agent : public QObject {
    Q_OBJECT
public:
    explicit Agent(QObject *parent = nullptr, int deadlineMs = 180000);
    ~Agent() override;
    bool available() const;
    QString executable() const;
    bool busy() const;
    void ask(const QString &projectPath, const QJsonObject &state, const QString &source,
             const QString &imagePath = {}, const QString &runId = {});
    void cancel();
    void setModel(const QString &model) { m_selectedModel = model; }
    static QJsonObject parseReply(const QByteArray &text, QString *error);
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
    void readOutput();
    void readLine(const QByteArray &line);
    void readMessage(const QJsonObject &message, bool complete);
    void observe(const QString &phase, bool force = false);
    void stopProcess();
    void failRun(const QString &code, const QString &message);
    QProcess m_process;
    QTimer m_timeout;
    bool m_cancelled = false;
    QString m_promptFile;
    QByteArray m_pendingOutput;
    QByteArray m_textOutput;
    QByteArray m_replyOutput;
    QString m_reportedModel;
    QString m_selectedModel, m_requestedModel;
    bool m_structuredOutput = false;
    QElapsedTimer m_clock;
    QString m_runId, m_phase, m_lastActivePhase, m_failureCode, m_lastEvent, m_providerOutcome;
    qint64 m_lastEventMs = -1, m_lastProviderMs = -1, m_lastPublishedMs = -1000;
    qint64 m_stdoutBytes = 0, m_stderrBytes = 0, m_promptBytes = 0;
    int m_eventCount = 0, m_deltaCount = 0, m_retryCount = 0;
    int m_deadlineMs;
    qint64 m_processGroup = 0;
    bool m_started = false, m_agentEnded = false, m_resolving = false;
};
