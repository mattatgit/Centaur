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
#include <QRegularExpression>

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
    connect(&m_session, &Session::annotationRejected, this, &Controller::annotationRejected);
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
    connect(&m_preview, &QProcess::readyReadStandardOutput, this, [this] {
        emit previewOutput(m_preview.readAllStandardOutput());
    });
    connect(&m_preview, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            m_previewStatus = m_nativeTestProgram.isEmpty() ? "Could not launch centaur-preview. Check its installation." : "Could not launch the native test app.";
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
        // Old GTK clients saved the host-assigned actor alias as the membership name.
        if (!connection.contains("displayName") && qEnvironmentVariable("CENTAUR_GTK_CLIENT") == "1")
            connection["displayName"] = m_preferences.value("author", m_author).toString();
        auto *project = new SharedProject(dataRoot(), connection, this); addShared(project); project->start();
    }
    m_session.start(background);
}
QString Controller::author() const { return remoteProject() ? m_shared.value(m_projectId)->author() : m_author; }
QString Controller::collaborationRole() const {
    if (!m_projectId.isEmpty()) return remoteProject() ? "Guest" : "Host";
    for (const auto &project : m_projects) if (!project.toMap()["remote"].toBool()) return "Host";
    return m_projects.isEmpty() ? QString() : QString("Guest");
}
bool Controller::hostsShare(const QString &id) const {
    return !m_shared.contains(id) && m_states.value(id)["sharing"].toObject()["enabled"].toBool();
}
QJsonArray Controller::endedShares() const {
    QJsonArray notices;
    for (const auto *project : m_shared) {
        if (!project->ended()) continue;
        const auto notice = project->endNotice();
        if (!notice.isEmpty()) notices.append(QJsonObject{{"id", project->id()}, {"name", notice["name"]},
            {"canKeep", !notice["copyId"].toString().isEmpty()}});
    }
    return notices;
}
void Controller::resolveEndedShare(const QString &id, bool retain) {
    m_session.send({{"type", "resolveEndedShare"}, {"projectId", id}, {"retain", retain}});
}
QJsonArray Controller::projectCollaborators(const QString &id) const {
    const auto sharing = m_states.value(id)["sharing"].toObject();
    const auto *remote = m_shared.value(id, nullptr);
    if (!remote && !sharing["enabled"].toBool()) return {};
    const auto participants = sharing["participants"].toArray();
    if (participants.size() >= 2) {
        const auto self = remote ? remote->participantId() : QString("host");
        QJsonArray roster;
        for (const auto &value : participants) {
            auto participant = value.toObject();
            participant["self"] = participant["id"] == self;
            if (participant["self"].toBool()) roster.prepend(participant);
            else roster.append(participant);
        }
        return roster;
    }

    const auto current = remote ? remote->author() : sharing["owner"].toString(m_author);
    QJsonArray result;
    QSet<QString> added;
    auto append = [&](const QString &name, bool self = false) {
        if (name.isEmpty() || added.contains(name.toCaseFolded())) return;
        added.insert(name.toCaseFolded());
        result.append(QJsonObject{{"name", name}, {"self", self}});
    };
    append(current, true);
    if (remote) append(sharing["owner"].toString());
    for (const auto &value : sharing["members"].toArray()) append(value.toString());
    // An invitation may enable a listener before anyone joins. A cached
    // guest project can also lack a roster from an older host.
    return result.size() >= 2 ? result : QJsonArray{};
}
QString Controller::participantId() const {
    if (remoteProject()) return m_shared.value(m_projectId)->participantId();
    return hostsShare(m_projectId) ? QString("host") : "local:" + m_author;
}
QJsonArray Controller::ownMemberships() const {
    return remoteProject() ? m_shared.value(m_projectId)->ownMemberships() : QJsonArray{};
}
QString Controller::drawingColor() const {
    const auto self = participantId();
    for (const auto &value : m_states.value(m_projectId)["sharing"].toObject()["participants"].toArray()) {
        const auto participant = value.toObject();
        if (participant["id"] == self) return participant["color"].toString("#138EF5");
    }
    return remoteProject() ? QString("#FF6157") : QString("#138EF5");
}
void Controller::refreshAvatar() {
    m_session.send({{"type", "refreshAvatar"}});
    for (auto *project : m_shared) project->refreshAvatar();
}
bool Controller::canContribute() const { return remoteProject() ? m_shared.value(m_projectId)->writable() : m_session.connected(); }
bool Controller::agentAvailable() const { return remoteProject() ? m_shared.value(m_projectId)->agentAvailable() : m_agentAvailable; }
bool Controller::agentBusy() const { return remoteProject() ? m_shared.value(m_projectId)->busy() :
    (!m_projectId.isEmpty() && (m_busyProject==m_projectId || !project().value("agentActivity").toMap().isEmpty())); }
bool Controller::updateBlocked() const {
    if (m_localSnapshot["updateBlocked"].toBool() || m_localSnapshot["localWindows"].toInt()>1 || joining() || inviting()) return true;
    for (auto *shared : m_shared) if (shared->busy() || shared->pendingCount() > 0) return true;
    return false;
}
QString Controller::connectionStatus() const {
    if (remoteProject()) {
        const auto *shared = m_shared.value(m_projectId);
        return shared->connected() ? "Guest connected" : shared->status();
    }
    return m_session.connected() ? "Host online" : "Host unavailable";
}
QString Controller::joinStatus() const { return m_shared.contains(m_joiningId) ? m_shared.value(m_joiningId)->status() : m_joinMessage; }
void Controller::invitePeople(const QString &address) {
    if (m_inviting) return;
    m_inviting = true; m_invitationCode.clear(); emit changed(); command({{"type", "invite"}, {"address", address}});
}
void Controller::stopSharing() { stopSharingProject(m_projectId); }
void Controller::stopSharingProject(const QString &id) {
    const bool preparing = id == m_projectId && m_inviting && !remoteProject();
    if (id.isEmpty() || (!hostsShare(id) && !preparing)) return;
    if (id == m_projectId) m_invitationCode.clear();
    route(id, {{"type", "stopSharing"}});
}
void Controller::copyInvitation() { QGuiApplication::clipboard()->setText(m_invitationCode); }
void Controller::joinFailure(const QString &code, const QString &message) {
    emit joinFailed(code, message);
    emit error(message);
}
void Controller::waitForJoin(SharedProject *project) {
    const auto id = project->id();
    m_joinMessage.clear(); m_joiningId = id; refresh();
    const auto attempt = ++m_joinAttempt;
    QTimer::singleShot(60000, project, [this,project,id,attempt] {
        if (m_joinAttempt != attempt || m_joiningId != id || project->connected()) return;
        // Keep the membership token. The host may have admitted this guest
        // just before the connection failed, even if its reply was lost.
        m_joiningId.clear(); refresh();
        joinFailure("connection","Could not reach the host. Check the connection and try again.");
    });
}
void Controller::joinProject(const QString &code, const QString &name) {
    if (!m_joiningId.isEmpty()) return;
    if (name.trimmed().isEmpty()) { joinFailure("name","Enter your name to join."); return; }
    QString error;
    auto connection = SharedProject::parseInvitation(code, &error);
    if (connection.isEmpty()) { joinFailure(error.contains("version") ? "version" : "invalid",error); return; }
    const auto id = connection["project"].toString();
    if (const auto *existing = m_shared.value(id, nullptr); existing && existing->failed()) {
        if (!existing->endNotice().isEmpty()) { joinFailure("unavailable","Respond to the previous sharing notice before rejoining this project."); return; }
        discardShared(id);
    }
    if (const auto *existing = m_shared.value(id, nullptr); existing && existing->leaving()) {
        joinFailure("unavailable","Wait for the host to confirm your departure before rejoining."); return;
    }
    if (auto *existing = m_shared.value(id)) {
        if (existing->connected()) { openProject(id); emit joined(); }
        else waitForJoin(existing);
        return;
    }
    if (m_states.contains(id)) { joinFailure("unavailable","This project is already on this computer."); return; }
    const auto chosenName = name.trimmed().left(50);
    connection["name"] = chosenName;
    connection["displayName"] = chosenName;
    auto *project = new SharedProject(dataRoot(), connection, this);
    if (!project->save(&error)) { delete project; joinFailure("unavailable","Could not save the invitation: " + error); return; }
    addShared(project); waitForJoin(project); project->start();
}
void Controller::addShared(SharedProject *project) {
    m_shared.insert(project->id(), project);
    connect(project, &SharedProject::error, this, [this,project](const QString &message) {
        if (project->id() == m_joiningId) {
            m_joiningId.clear();
            refresh();
            joinFailure(project->joinErrorCode(), message);
        } else emit error(message);
    });
    connect(project, &SharedProject::annotationRejected, this, &Controller::annotationRejected);
    connect(project, &SharedProject::changed, this, &Controller::refresh);
    refresh();
}
void Controller::cancelJoin() { if (!m_joiningId.isEmpty()) discardShared(m_joiningId); }
void Controller::leaveProject(const QString &id) {
    if (auto *project = m_shared.value(id, nullptr); project && !project->removed()) {
        if (project->failed()) discardShared(id);
        else project->leave();
    }
}
void Controller::discardShared(const QString &id) {
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
void Controller::setSurfaceCount(int count) {
    m_surfaceCount = count;
    if (count > 0) m_previewStatus = "Native app running";
    emit previewChanged();
}
void Controller::configureNativeAppTest(const QString &program, const QSize &size) {
    m_nativeTestProgram = program;
    m_previewSize = size;
}
void Controller::setAuthor(const QString &author) {
    if (author.trimmed().isEmpty()) return;
    m_author = author.trimmed().left(50);
    savePreferences();
    for (auto *project : m_shared) project->setDisplayName(m_author);
    m_session.send({{"type","ownerDisplayName"},{"name",m_author}});
    emit changed();
}

bool Controller::setAgentDefaults(const QJsonObject &settings) {
    if (settings.contains("agentName")) {
        const auto name = settings["agentName"].toString().trimmed().remove('@').left(30);
        if (name.isEmpty() || name.contains(QRegularExpression("\\s"))) { emit error("Use a single agent name without spaces."); return false; }
        m_preferences.setValue("agent/name", name);
    }
    if (settings.contains("model")) m_preferences.setValue("agent/model", settings["model"].toString().left(300));
    savePreferences(); emit preferencesChanged(); return preferencesSaved();
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
        if (state.isEmpty() || shared->removed() || shared->leaving()) continue;
        state["remote"] = true; state["connectionStatus"] = shared->status();
        m_states.insert(shared->id(), state);
        m_projects.append(QVariantMap{{"id", shared->id()}, {"name", state["name"].toString()}, {"description", state["description"].toString()}, {"appFormat", state["appFormat"].toString()}, {"updated", state["updated"].toString()}, {"remote", true}, {"connected", shared->connected()}});
    }
    m_agentAvailable = m_localSnapshot["agentAvailable"].toBool();
    m_agentExecutable = m_localSnapshot["agentExecutable"].toString();
    m_busyProject = m_localSnapshot["busyProject"].toString();
    if (!m_projectId.isEmpty() && !m_states.contains(m_projectId)) closeProject();

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
void Controller::createGtkProject(const QString &name, const QString &description, bool generate) {
    QJsonObject command{{"type", "create"}, {"name", name}, {"description", description}, {"appFormat", "gtk4-v1"}};
    if (generate) { command["createPrompt"]=description; command["author"]=m_author; }
    m_session.send(command);
}
void Controller::importGtkProject(const QJsonObject &data) {
    auto command=data; command["type"]="importProject"; command["author"]=m_author;
    m_session.send(command);
}
void Controller::importAction(const QString &type, const QJsonObject &source) {
    if (remoteProject()) { emit error("Run or retry source imports on the project host."); return; }
    if (type!="retryImport" && type!="runImport") return;
    route(m_projectId,{{"type",type},{"source",source}});
}
QJsonObject Controller::importSource() const {
    if (remoteProject() || project().value("import").toMap().isEmpty()) return {};
    return Workspace(dataRoot()).load(m_projectId).value("importLocal").toObject()["source"].toObject();
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
bool Controller::sendMessage(const QString &text, const QString &image, int imageRevision, const QJsonObject &comment, const QJsonArray &attachments) {
    return route(m_projectId, {{"type", "message"}, {"text", text}, {"image", image}, {"imageRevision", imageRevision}, {"comment", comment}, {"attachments", attachments}});
}
void Controller::addAnnotation(const QVariantMap &annotation) { command({{"type", "annotation"}, {"annotation", QJsonObject::fromVariantMap(annotation)}}); }
bool Controller::submitAnnotation(const QJsonObject &annotation, int revision) {
    return route(m_projectId, {{"type", "annotation"}, {"annotation", annotation}, {"baseRevision", revision}});
}
void Controller::undoAnnotation() { command({{"type", "undo"}}); }
void Controller::acceptProposal() {
    command({{"type", "accept"}, {"proposalId", m_states[m_projectId]["proposal"].toObject()["id"]}});
}
void Controller::voteOnProposal(const QString &proposalId, const QString &choice, bool reject) {
    command({{"type", reject ? "rejectProposal" : "accept"}, {"proposalId", proposalId}, {"choice", choice}});
}
void Controller::renameAgent(const QString &name) { command({{"type", "agentName"}, {"name", name}}); }
void Controller::renameProjectAgent(const QString &id, const QString &name) { route(id, {{"type", "agentName"}, {"name", name}}); }
void Controller::cancelAgent() { command({{"type", "cancel"}}); }

void Controller::startPreview() {
    if (project().value("appFormat").toString() == "gtk4-v1") { m_previewStatus = "Open this GTK4 project in Centaur GTK4."; emit previewChanged(); return; }
    if (!embeddingSupported() || m_projectId.isEmpty() || m_stopping
        || m_preview.state() != QProcess::NotRunning) return;
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("WAYLAND_DISPLAY", socketName());
    env.insert("QT_QPA_PLATFORM", "wayland");
    env.insert("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1");
    if (!m_nativeTestProgram.isEmpty()) {
        // Force the private compositor, with no X11/desktop fallback. Isolate
        // Landline's profile, keys and caches from the normal installed app.
        env.remove("DISPLAY");
        env.remove("WAYLAND_SOCKET");
        env.insert("XDG_SESSION_TYPE", "wayland");
        // Landline uses an independently pinned Nix runtime. Its EGL driver
        // must match that runtime, rather than Centaur's newer libc/Mesa.
        const auto vendor = qEnvironmentVariable("CENTAUR_TEST_NATIVE_EGL_VENDOR");
        const auto drivers = qEnvironmentVariable("CENTAUR_TEST_NATIVE_DRI");
        if (!vendor.isEmpty()) env.insert("__EGL_VENDOR_LIBRARY_FILENAMES", vendor);
        if (!drivers.isEmpty()) env.insert("LIBGL_DRIVERS_PATH", drivers);
        for (const auto &kind : {QString("config"), QString("data"), QString("cache")}) {
            const auto path = dataRoot() + "/native-app-runtime/" + kind;
            if (!QDir().mkpath(path)) {
                m_previewStatus = "Could not prepare the temporary app data.";
                emit previewChanged();
                return;
            }
            env.insert("XDG_" + kind.toUpper() + "_HOME", path);
        }
    }
    // Shared-memory buffers support software rendering on entry-level hardware.
    if (qEnvironmentVariable("QT_QUICK_BACKEND") == "software") env.insert("QT_WAYLAND_CLIENT_BUFFER_INTEGRATION", "shm");
    m_preview.setProcessEnvironment(env);
    const auto path = projectPath();
    m_preview.setWorkingDirectory(path);
    const auto executable = m_nativeTestProgram.isEmpty()
        ? qEnvironmentVariable("CENTAUR_PREVIEW", QCoreApplication::applicationDirPath() + "/centaur-preview")
        : m_nativeTestProgram;
    m_preview.start(executable, m_nativeTestProgram.isEmpty() ? QStringList{path + "/App.qml"} : QStringList{});
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
