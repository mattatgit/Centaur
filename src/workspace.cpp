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

static bool git(const QString &path, const QStringList &args, QString *error, QByteArray *output = nullptr) {
    QProcess process;
    process.setWorkingDirectory(path);
    process.start("git", args);
    if (!process.waitForFinished(10000) || process.exitCode() != 0) {
        if (error) *error = QString::fromUtf8(process.readAllStandardError()).trimmed();
        if (error && error->isEmpty()) *error = "Git is unavailable or timed out.";
        return false;
    }
    if (output) *output = process.readAllStandardOutput();
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

QString Workspace::createProject(const QString &name, const QString &description, QString *error, const QString &format, bool imported) {
    if (name.trimmed().isEmpty() || name.size() > 100) {
        if (error) *error = "Give the project a name of up to 100 characters.";
        return {};
    }
    if (!format.isEmpty() && format != "gtk4-v1") {
        if (error) *error = "Unsupported application format.";
        return {};
    }
    const bool gtk = format == "gtk4-v1";
    const auto filename = gtk ? QString("App.gtk.json") : QString("App.qml");
    const QString id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    const auto path = projectPath(id);
    QDir().mkpath(path + "/.centaur");
    if (imported) QFile::setPermissions(path+"/.centaur",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner);
    QFile starter(gtk ? ":/templates/App.gtk.json" : ":/templates/App.qml");
    if (!starter.open(QIODevice::ReadOnly)) {
        if (error) *error = "The native starter app resource is missing.";
        QDir(path).removeRecursively();
        return {};
    }
    const QByteArray source = starter.readAll();
    if (source.isEmpty() || (!imported && !writeFile(path + "/" + filename, source, error))
        || !writeFile(path + "/.gitignore", ".centaur/\n", error)
        || !writeFile(path + "/README.md", ("# " + name.trimmed() + "\n\n" + description +
            (imported ? "\n\nImported source and separate adaptations are preserved under .centaur/import. No imported code runs automatically.\n"
                : gtk ? "\n\nNative GTK4 app. Source bundle: App.gtk.json; behaviour, GtkBuilder UI and CSS are separate.\n" : "\n\nNative Qt Quick app. Run with `centaur-preview App.qml`.\n")).toUtf8(), error)
        || !git(path, {"init", "-b", "main"}, error)
        || !git(path, imported ? QStringList{"add", "README.md", ".gitignore"} : QStringList{"add", filename, "README.md", ".gitignore"}, error)
        || !git(path, {"-c", "user.name=Centaur", "-c", "user.email=centaur@localhost", "commit", "-m", imported ? "Start imported project" : "Start native app"}, error)) {
        QDir(path).removeRecursively();
        return {};
    }
    QJsonObject state{{"id", id}, {"name", name.trimmed()}, {"description", description.trimmed()},
        {"updated", now()}, {"revision", 1}, {"epoch", 0}, {"agentName", "centaur"},
        {"messages", QJsonArray()}, {"annotations", QJsonArray()}, {"decisions", QJsonArray()},
        {"contributors", QJsonArray()}, {"proposal", QJsonObject()}};
    if (gtk) state["appFormat"] = format;
    if (!save(id, state, error)) { QDir(path).removeRecursively(); return {}; }
    return id;
}

QString Workspace::sourceName(const QJsonObject &state) {
    return state["appFormat"] == "gtk4-v1" ? "App.gtk.json" : "App.qml";
}

QString Workspace::source(const QString &id) const {
    const auto path = projectPath(id);
    if (path.isEmpty()) return {};
    QFile file(path + "/" + sourceName(load(id)));
    return file.open(QIODevice::ReadOnly) ? QString::fromUtf8(file.readAll()) : QString();
}

bool Workspace::deleteProject(const QString &id, QString *error) {
    const auto path = projectPath(id);
    if (path.isEmpty() || load(id).isEmpty()) {
        if (error) *error = "That project is unavailable.";
        return false;
    }
    // Remove the whole project atomically from the live collection, preserving
    // source, history and conversation together for manual recovery.
    const auto trash = m_root + "/trash";
    if (!QDir().mkpath(trash) || !QDir().rename(path, trash + "/" + id)) {
        if (error) *error = "Could not delete the project. Its files have been kept.";
        return false;
    }
    return true;
}

QJsonArray Workspace::history(const QString &id, QString *error) const {
    const auto path = projectPath(id);
    if (path.isEmpty()) { if (error) *error = "Invalid project."; return {}; }
    QByteArray output;
    // Only metadata enters the model context. Full source stays in Git until a
    // specific restore is requested; bound context for modest hardware.
    QStringList args{"log", "-100", "--format=%H%x00%cI%x00%s%x00"};
    // Imported projects begin with an identity-only root commit, not an app.
    // Keep subsequent checkpoints, including intentional empty app commits.
    if (!load(id).value("import").toObject().isEmpty()) args << "--min-parents=1";
    if (!git(path, args, error, &output)) return {};
    const auto fields = output.split('\0');
    QJsonArray history;
    for (int i = 0; i + 2 < fields.size(); i += 3) {
        history.append(QJsonObject{{"checkpoint", QString::fromUtf8(fields[i]).trimmed()},
            {"time", QString::fromUtf8(fields[i + 1])}, {"summary", QString::fromUtf8(fields[i + 2])}});
    }
    return history;
}

QString Workspace::sourceAt(const QString &id, const QString &checkpoint, QString *error) const {
    const auto path = projectPath(id);
    static const QRegularExpression valid("^(?:[a-f0-9]{40}|[a-f0-9]{64})$");
    if (path.isEmpty() || !valid.match(checkpoint).hasMatch()) {
        if (error) *error = "That saved app could not be identified.";
        return {};
    }
    if (!git(path, {"merge-base", "--is-ancestor", checkpoint, "HEAD"}, nullptr)) {
        if (error) *error = "That saved app is not in this project's history.";
        return {};
    }
    QByteArray output;
    if (!git(path, {"show", checkpoint + ":" + sourceName(load(id))}, error, &output)) return {};
    const auto source = QString::fromUtf8(output);
    if (source.trimmed().isEmpty() || source.size() > 256000) {
        if (error) *error = "That saved app is empty or too large for this prototype.";
        return {};
    }
    return source;
}

bool Workspace::applySource(const QString &id, const QString &qml, const QString &summary, QString *error) {
    const auto path = projectPath(id);
    if (path.isEmpty() || qml.trimmed().isEmpty()) { if (error) *error = "Missing native app source."; return false; }
    const auto filename = sourceName(load(id));
    const auto previous = source(id).toUtf8();
    if (!writeFile(path + (filename == "App.qml" ? "/.centaur/previous.qml" : "/.centaur/previous-App.gtk.json"), previous, error)
        || !writeFile(path + "/" + filename, qml.toUtf8(), error)) return false;
    if (!git(path, {"add", filename}, error)
        || !git(path, {"-c", "user.name=Centaur", "-c", "user.email=centaur@localhost",
            "commit", "--allow-empty", "-m", summary.left(200)}, error)) {
        writeFile(path + "/" + filename, previous);
        git(path, {"reset", "--", filename}, nullptr);
        return false;
    }
    return true;
}
