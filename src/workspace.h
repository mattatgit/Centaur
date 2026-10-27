#pragma once
#include <QJsonObject>
#include <QJsonArray>
#include <QVariantList>
#include <QString>

class Workspace {
public:
    explicit Workspace(QString root);
    QString root() const { return m_root; }
    QVariantList projects() const;
    QString createProject(const QString &name, const QString &description, QString *error);
    bool deleteProject(const QString &id, QString *error = nullptr);
    QJsonObject load(const QString &id) const;
    bool save(const QString &id, const QJsonObject &state, QString *error = nullptr) const;
    QString projectPath(const QString &id) const;
    QString source(const QString &id) const;
    QJsonArray history(const QString &id, QString *error = nullptr) const;
    QString sourceAt(const QString &id, const QString &checkpoint, QString *error = nullptr) const;
    bool applySource(const QString &id, const QString &qml, const QString &summary, QString *error);
    static bool writeFile(const QString &path, const QByteArray &contents, QString *error = nullptr);
    static QString now();
private:
    QString m_root;
};
