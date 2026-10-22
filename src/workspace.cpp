#include "workspace.h"
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSaveFile>
#include <QDateTime>
#include <QUuid>
#include <QProcess>
#include <QRegularExpression>
#include <algorithm>

static bool git(const QString &path, const QStringList &args, QString *error) {
    QProcess process;
    process.setWorkingDirectory(path);
    process.start("git", args);
    if (!process.waitForFinished(10000) || process.exitCode() != 0) {
        if (error) *error = QString::fromUtf8(process.readAllStandardError()).trimmed();
        if (error && error->isEmpty()) *error = "Git is unavailable or timed out.";
        return false;
    }
    return true;
}

Workspace::Workspace(QString root) : m_root(QDir::cleanPath(root)) {
    QDir().mkpath(m_root + "/projects");
}

QString Workspace::now() { return QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs); }

QString Workspace::projectPath(const QString &id) const {
    static const QRegularExpression valid("^[a-f0-9-]{36}$");
    return valid.match(id).hasMatch() ? m_root + "/projects/" + id : QString();
}

bool Workspace::writeFile(const QString &path, const QByteArray &contents, QString *error) {
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(contents) != contents.size() || !file.commit()) {
        if (error) *error = file.errorString();
        return false;
    }
    return true;
}

QJsonObject Workspace::load(const QString &id) const {
    const auto path = projectPath(id);
    if (path.isEmpty()) return {};
    QFile file(path + "/.centaur/state.json");
    if (!file.open(QIODevice::ReadOnly)) return {};
    return QJsonDocument::fromJson(file.readAll()).object();
}

bool Workspace::save(const QString &id, const QJsonObject &state, QString *error) const {
    const auto path = projectPath(id);
    if (path.isEmpty()) { if (error) *error = "Invalid project."; return false; }
    return writeFile(path + "/.centaur/state.json", QJsonDocument(state).toJson(), error);
}

QVariantList Workspace::projects() const {
    QVariantList result;
    for (const auto &id : QDir(m_root + "/projects").entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        const auto state = load(id);
        if (state.isEmpty() || state["archived"].toBool()) continue;
        result.append(QVariantMap{{"id", id}, {"name", state["name"].toString()},
            {"description", state["description"].toString()}, {"updated", state["updated"].toString()},
            {"revision", state["revision"].toInt()}, {"path", projectPath(id)}});
    }
    std::sort(result.begin(), result.end(), [](const QVariant &a, const QVariant &b) {
        return a.toMap()["updated"].toString() > b.toMap()["updated"].toString();
    });
    return result;
}

QString Workspace::createProject(const QString &name, const QString &description, QString *error) {
    if (name.trimmed().isEmpty() || name.size() > 100) {
        if (error) *error = "Give the project a name of up to 100 characters.";
        return {};
    }
    const QString id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    const auto path = projectPath(id);
    QDir().mkpath(path + "/.centaur");
    QFile starter(":/templates/App.qml");
    if (!starter.open(QIODevice::ReadOnly)) {
        if (error) *error = "The native starter app resource is missing.";
        QDir(path).removeRecursively();
        return {};
    }
    const QByteArray source = starter.readAll();
    if (source.isEmpty() || !writeFile(path + "/App.qml", source, error)
        || !writeFile(path + "/.gitignore", ".centaur/\n", error)
        || !writeFile(path + "/README.md", ("# " + name.trimmed() + "\n\n" + description +
            "\n\nNative Qt Quick app. Run with `centaur-preview App.qml`.\n").toUtf8(), error)
        || !git(path, {"init", "-b", "main"}, error)
        || !git(path, {"add", "App.qml", "README.md", ".gitignore"}, error)
        || !git(path, {"-c", "user.name=Centaur", "-c", "user.email=centaur@localhost", "commit", "-m", "Start native app"}, error)) {
        QDir(path).removeRecursively();
        return {};
    }
    QJsonObject state{{"id", id}, {"name", name.trimmed()}, {"description", description.trimmed()},
        {"updated", now()}, {"revision", 1}, {"epoch", 0}, {"agentName", "centaur"},
        {"messages", QJsonArray()}, {"annotations", QJsonArray()}, {"decisions", QJsonArray()},
        {"contributors", QJsonArray()}, {"proposal", QJsonObject()}};
    if (!save(id, state, error)) { QDir(path).removeRecursively(); return {}; }
    return id;
}

QString Workspace::source(const QString &id) const {
    const auto path = projectPath(id);
    if (path.isEmpty()) return {};
    QFile file(path + "/App.qml");
    return file.open(QIODevice::ReadOnly) ? QString::fromUtf8(file.readAll()) : QString();
}

bool Workspace::applySource(const QString &id, const QString &qml, const QString &summary, QString *error) {
    const auto path = projectPath(id);
    if (path.isEmpty() || qml.trimmed().isEmpty()) { if (error) *error = "Missing native app source."; return false; }
    const auto previous = source(id).toUtf8();
    if (!writeFile(path + "/.centaur/previous.qml", previous, error)
        || !writeFile(path + "/App.qml", qml.toUtf8(), error)) return false;
    if (!git(path, {"add", "App.qml"}, error)
        || !git(path, {"-c", "user.name=Centaur", "-c", "user.email=centaur@localhost",
            "commit", "--allow-empty", "-m", summary.left(200)}, error)) {
        writeFile(path + "/App.qml", previous);
        git(path, {"reset", "--", "App.qml"}, nullptr);
        return false;
    }
    return true;
}
