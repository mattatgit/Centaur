#pragma once
#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QJsonObject>

// The agent proposes source; only the project coordinator can apply it.
class Agent : public QObject {
    Q_OBJECT
public:
    explicit Agent(QObject *parent = nullptr);
    bool available() const;
    bool busy() const;
    void ask(const QString &projectPath, const QJsonObject &state, const QString &source,
             const QString &imagePath = {});
    void cancel();
    static QJsonObject parseReply(const QByteArray &text, QString *error);
signals:
    void completed(const QJsonObject &reply);
    void failed(const QString &message);
private:
    QString executable() const;
    QProcess m_process;
    QTimer m_timeout;
    bool m_cancelled = false;
    QString m_promptFile;
};
