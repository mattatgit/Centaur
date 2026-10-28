#include "controller.h"
#include <QCoreApplication>
#include <QDesktopServices>
#include <QJsonArray>
#include <QUrl>
#include <QUuid>
#include <QFileInfo>
#include <QDir>
#include <QJsonDocument>
#include <QFile>
#include <QGuiApplication>
#include <QClipboard>

Controller::Controller(QString root, QObject *parent) : QObject(parent),
    m_preferences(root + "/preferences.ini", QSettings::IniFormat), m_session(root) {
    m_author = qEnvironmentVariable("CENTAUR_AUTHOR", m_preferences.value("author", qEnvironmentVariable("USER", "You")).toString());
    m_gridEnabled = m_preferences.value("grid/enabled", false).toBool();
    m_gridSize = qBound(2, m_preferences.value("grid/size", 8).toInt(), 64);
    m_gridOpacity = qBound(0, m_preferences.value("grid/opacity", 50).toInt(), 100);
    const QColor savedColor(m_preferences.value("grid/color", "#BAE6FF").toString());
    if (savedColor.isValid()) m_gridColor = savedColor;
    m_previewStatus = embeddingSupported() ? "Opening native app…" : "Native embedding requires Linux";
    connect(&m_session, &Session::snapshot, this, &Controller::receive);
    connect(&m_session, &Session::error, this, [this](const QString &message) { m_inviting = false; emit changed(); emit error(message); });
    connect(&m_session, &Session::connectionChanged, this, [this] { if (!m_session.connected()) m_inviting = false; emit changed(); });
    connect(&m_preview, &QProcess::started, this, [this] {
        m_previewStatus = "Connecting native app…"; emit previewChanged();
    });
    connect(&m_preview, &QProcess::readyReadStandardError, this, [this] {
        const auto output = m_preview.readAllStandardError();
        emit previewOutput(output);
        if (output.contains("CENTAUR_READY")) {
            m_previewStatus = "Native app running"; emit previewChanged();
        }
    });
    connect(&m_preview, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            m_previewStatus = "Could not launch centaur-preview. Check its installation.";
            emit previewChanged();
        }
    });
    connect(&m_preview, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
        [this](int code, QProcess::ExitStatus status) {
            if (m_stopping) return;
            m_previewStatus = (code == 0 && status == QProcess::NormalExit) ? "App closed · Restart to reopen" : "App stopped unexpectedly · Restart to try again";
            emit previewChanged();
        });
}
Controller::~Controller() { stopPreview(); }
void Controller::start(bool background) {
    const QDir shared(dataRoot() + "/shared");
    for (const auto &id : shared.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        QFile file(shared.filePath(id + "/connection.json"));
        if (!file.open(QIODevice::ReadOnly)) continue;
        auto connection = QJsonDocument::fromJson(file.readAll()).object();
        if (connection["project"] != id || QUuid(id).isNull() || id.size() != 36) continue;
        auto *project = new SharedProject(dataRoot(), connection, this); addShared(project); project->start();
    }
    m_session.start(background);
}
QString Controller::author() const { return remoteProject() ? m_shared.value(m_projectId)->author() : m_author; }
bool Controller::canContribute() const { return remoteProject() ? m_shared.value(m_projectId)->writable() : m_session.connected(); }
bool Controller::agentAvailable() const { return remoteProject() ? m_shared.value(m_projectId)->agentAvailable() : m_agentAvailable; }
bool Controller::agentBusy() const { return remoteProject() ? m_shared.value(m_projectId)->busy() : m_busyProject == m_projectId && !m_projectId.isEmpty(); }
QString Controller::connectionStatus() const { return remoteProject() ? m_shared.value(m_projectId)->status() : m_session.connected() ? "Local project" : "Local host unavailable"; }
QString Controller::joinStatus() const { return m_shared.contains(m_joiningId) ? m_shared.value(m_joiningId)->status() : m_joinMessage; }
void Controller::invitePeople(const QString &address) {
    if (m_inviting) return;
    m_inviting = true; m_invitationCode.clear(); emit changed(); command({{"type", "invite"}, {"address", address}});
}
void Controller::stopSharing() { m_invitationCode.clear(); command({{"type", "stopSharing"}}); }
void Controller::copyInvitation() { QGuiApplication::clipboard()->setText(m_invitationCode); }
void Controller::joinProject(const QString &code, const QString &name) {
    if (name.trimmed().isEmpty()) { emit error("Enter your name to join."); return; }
    QString error;
    auto connection = SharedProject::parseInvitation(code, &error);
    if (connection.isEmpty()) { emit this->error(error); return; }
    const auto id = connection["project"].toString();
    if (m_shared.contains(id) && m_shared.value(id)->failed()) leaveProject(id);
    if (m_shared.contains(id)) { openProject(id); emit joined(); return; }
    if (m_states.contains(id)) { emit this->error("This project is already on this computer."); return; }
    connection["name"] = name.trimmed().left(50);
    auto *project = new SharedProject(dataRoot(), connection, this);
    if (!project->save(&error)) { delete project; emit this->error("Could not save the invitation: " + error); return; }
    m_joinMessage.clear(); m_joiningId = id; addShared(project); project->start();
}
void Controller::addShared(SharedProject *project) {
    m_shared.insert(project->id(), project);
    connect(project, &SharedProject::error, this, &Controller::error);
    connect(project, &SharedProject::changed, this, &Controller::refresh);
    refresh();
}
void Controller::cancelJoin() { if (!m_joiningId.isEmpty()) leaveProject(m_joiningId); }
void Controller::leaveProject(const QString &id) {
    auto *project = m_shared.take(id);
    if (!project) return;
    if (m_joiningId == id) m_joiningId.clear();
    QFile::remove(project->path() + "/connection.json");
    project->release(); project->deleteLater(); refresh();
}
QString Controller::projectPath() const { return remoteProject() ? m_shared.value(m_projectId)->path() : dataRoot() + "/projects/" + m_projectId; }

void Controller::openStarterProject() { m_session.send({{"type", "openStarter"}}); }
bool Controller::embeddingSupported() const {
#ifdef CENTAUR_WAYLAND
    return true;
#else
    return false;
#endif
}
QString Controller::socketName() const { return "centaur-preview-" + QString::number(QCoreApplication::applicationPid()); }
void Controller::setSurfaceCount(int count) { m_surfaceCount = count; emit previewChanged(); }
void Controller::setAuthor(const QString &author) {
    if (author.trimmed().isEmpty()) return;
    m_author = author.trimmed().left(50); savePreferences(); emit changed();
}

void Controller::savePreferences() {
    m_preferences.setValue("author", m_author);
    m_preferences.setValue("grid/enabled", m_gridEnabled);
    m_preferences.setValue("grid/size", m_gridSize);
    m_preferences.setValue("grid/opacity", m_gridOpacity);
    m_preferences.setValue("grid/color", m_gridColor.name());
    m_preferences.sync();
    if (m_preferences.status() != QSettings::NoError) emit error("Could not save your preferences.");
}
void Controller::setGridEnabled(bool value) {
    if (m_gridEnabled == value) return;
    m_gridEnabled = value; savePreferences(); emit preferencesChanged();
}
void Controller::setGridSize(int value) {
    value = qBound(2, value, 64);
    if (m_gridSize == value) return;
    m_gridSize = value; savePreferences(); emit preferencesChanged();
}
void Controller::setGridOpacity(int value) {
    value = qBound(0, value, 100);
    if (m_gridOpacity == value) return;
    m_gridOpacity = value; savePreferences(); emit preferencesChanged();
}
void Controller::setGridColor(const QColor &value) {
    if (!value.isValid() || m_gridColor == value) return;
    m_gridColor = value; savePreferences(); emit preferencesChanged();
}
void Controller::revealData() { QDesktopServices::openUrl(QUrl::fromLocalFile(dataRoot())); }

void Controller::receive(const QJsonObject &data) {
    if (data["type"] == "created" || data["type"] == "opened") {
        openProject(data["projectId"].toString()); return;
    }
    if (data["type"] == "invitation") { m_inviting = false; if (data["projectId"] != m_projectId) { emit changed(); return; } m_invitationCode = data["code"].toString(); emit changed(); return; }
    if (data["type"] != "snapshot") return;
    m_localSnapshot = data; refresh();
}
void Controller::refresh() {
    const auto oldRevision = project()["revision"].toInt();
    m_projects = m_localSnapshot["projects"].toArray().toVariantList();
    m_states.clear();
    for (const auto &value : m_localSnapshot["states"].toArray()) {
        const auto state = value.toObject(); m_states.insert(state["id"].toString(), state);
    }
    for (auto *shared : m_shared) {
        auto state = shared->state();
        if (state.isEmpty() || shared->removed()) continue;
        state["remote"] = true; state["connectionStatus"] = shared->status();
        m_states.insert(shared->id(), state);
        m_projects.append(QVariantMap{{"id", shared->id()}, {"name", state["name"].toString()}, {"description", state["description"].toString()}, {"remote", true}, {"connected", shared->connected()}});
    }
    m_agentAvailable = m_localSnapshot["agentAvailable"].toBool();
    m_agentExecutable = m_localSnapshot["agentExecutable"].toString();
    m_busyProject = m_localSnapshot["busyProject"].toString();
    if (!m_projectId.isEmpty() && !m_states.contains(m_projectId)) closeProject();
    if (!m_joiningId.isEmpty() && m_shared.value(m_joiningId)->failed()) { m_joinMessage = m_shared.value(m_joiningId)->status(); m_joiningId.clear(); }
    if (!m_joiningId.isEmpty() && m_shared.value(m_joiningId)->connected()) {
        const auto id = m_joiningId; m_joiningId.clear(); openProject(id); emit joined();
    }
    emit changed();
    if (oldRevision > 0 && project()["revision"].toInt() != oldRevision && previewRunning()) restartPreview();
}

void Controller::command(QJsonObject data) {
    route(m_projectId, data);
}
bool Controller::route(const QString &id, QJsonObject data) {
    data["projectId"] = id; data["author"] = m_author;
    if (m_shared.contains(id)) return m_shared.value(id)->send(data);
    if (!m_session.connected()) { emit error("The local host is unavailable. Your draft stays here."); return false; }
    m_session.send(data); return true;
}
void Controller::createProject(const QString &name, const QString &description) {
    m_session.send({{"type", "create"}, {"name", name}, {"description", description}});
}
void Controller::openProject(const QString &id) {
    if (!m_states.contains(id)) return;
    if (m_projectId != id) { stopPreview(); m_invitationCode.clear(); }
    m_projectId = id; emit changed();
}
void Controller::closeProject() { stopPreview(); m_projectId.clear(); m_invitationCode.clear(); emit changed(); }
void Controller::archiveProject(const QString &id) {
    route(id, {{"type", "archive"}});
}
void Controller::renameProject(const QString &id, const QString &name) {
    route(id, {{"type", "rename"}, {"name", name}});
}
void Controller::deleteProject(const QString &id) {
    route(id, {{"type", "delete"}});
}
bool Controller::sendMessage(const QString &text, const QString &image, int imageRevision) {
    return route(m_projectId, {{"type", "message"}, {"text", text}, {"image", image}, {"imageRevision", imageRevision}});
}
void Controller::addAnnotation(const QVariantMap &annotation) { command({{"type", "annotation"}, {"annotation", QJsonObject::fromVariantMap(annotation)}}); }
void Controller::undoAnnotation() { command({{"type", "undo"}}); }
void Controller::acceptProposal() {
    command({{"type", "accept"}, {"proposalId", m_states[m_projectId]["proposal"].toObject()["id"]}});
}
void Controller::renameAgent(const QString &name) { command({{"type", "agentName"}, {"name", name}}); }
void Controller::cancelAgent() { command({{"type", "cancel"}}); }

void Controller::startPreview() {
    if (!embeddingSupported() || m_projectId.isEmpty() || m_stopping
        || m_preview.state() != QProcess::NotRunning) return;
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("WAYLAND_DISPLAY", socketName());
    env.insert("QT_QPA_PLATFORM", "wayland");
    env.insert("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1");
    // Shared-memory buffers support software rendering on entry-level hardware.
    if (qEnvironmentVariable("QT_QUICK_BACKEND") == "software") env.insert("QT_WAYLAND_CLIENT_BUFFER_INTEGRATION", "shm");
    m_preview.setProcessEnvironment(env);
    const auto path = projectPath();
    m_preview.setWorkingDirectory(path);
    const auto executable = qEnvironmentVariable("CENTAUR_PREVIEW", QCoreApplication::applicationDirPath() + "/centaur-preview");
    m_preview.start(executable, {path + "/App.qml"});
    emit previewChanged();
}
void Controller::stopPreview() {
    if (m_stopping) return;
    m_stopping = true;
    // Release compositor views while their QML context and client surfaces are
    // alive. Killing the client during QML teardown can reenter model removal.
    emit previewStopping();
    if (m_preview.state() != QProcess::NotRunning) {
        m_preview.terminate();
        if (!m_preview.waitForFinished(800)) { m_preview.kill(); m_preview.waitForFinished(800); }
    }
    m_stopping = false;
    m_surfaceCount = 0;
    emit previewChanged();
}
void Controller::restartPreview() { stopPreview(); startPreview(); }
QString Controller::capturePath() const {
    if (m_projectId.isEmpty()) return {};
    QDir().mkpath(projectPath() + "/.centaur");
    return projectPath() + "/.centaur/context-"
        + QUuid::createUuid().toString(QUuid::WithoutBraces) + ".png";
}
void Controller::revealProject() {
    if (!m_projectId.isEmpty()) QDesktopServices::openUrl(QUrl::fromLocalFile(projectPath()));
}
