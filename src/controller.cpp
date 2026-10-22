#include "controller.h"
#include <QCoreApplication>
#include <QDesktopServices>
#include <QJsonArray>
#include <QUrl>
#include <QUuid>
#include <QFileInfo>

Controller::Controller(QString root, QObject *parent) : QObject(parent), m_session(root) {
    m_author = qEnvironmentVariable("CENTAUR_AUTHOR", qEnvironmentVariable("USER", "You"));
    m_previewStatus = embeddingSupported() ? "Opening native app…" : "Native embedding requires Linux";
    connect(&m_session, &Session::snapshot, this, &Controller::receive);
    connect(&m_session, &Session::error, this, &Controller::error);
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
void Controller::start() { m_session.start(); }
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
    m_author = author.trimmed().left(50); emit changed();
}

void Controller::receive(const QJsonObject &data) {
    if (data["type"] == "created") { openProject(data["projectId"].toString()); return; }
    if (data["type"] != "snapshot") return;
    const auto oldRevision = project()["revision"].toInt();
    m_projects = data["projects"].toArray().toVariantList();
    m_states.clear();
    for (const auto &value : data["states"].toArray()) {
        const auto state = value.toObject(); m_states.insert(state["id"].toString(), state);
    }
    m_agentAvailable = data["agentAvailable"].toBool();
    m_busyProject = data["busyProject"].toString();
    if (!m_projectId.isEmpty() && !m_states.contains(m_projectId)) closeProject();
    emit changed();
    if (oldRevision > 0 && project()["revision"].toInt() != oldRevision && previewRunning()) restartPreview();
}

void Controller::command(QJsonObject data) {
    data["projectId"] = m_projectId;
    data["author"] = m_author;
    m_session.send(data);
}
void Controller::createProject(const QString &name, const QString &description) {
    m_session.send({{"type", "create"}, {"name", name}, {"description", description}});
}
void Controller::openProject(const QString &id) {
    if (!m_states.contains(id)) return;
    if (m_projectId != id) stopPreview();
    m_projectId = id; emit changed();
}
void Controller::closeProject() { stopPreview(); m_projectId.clear(); emit changed(); }
void Controller::archiveProject(const QString &id) {
    m_session.send({{"type", "archive"}, {"projectId", id}, {"author", m_author}});
}
void Controller::sendMessage(const QString &text, const QString &image, int imageRevision) {
    command({{"type", "message"}, {"text", text}, {"image", image}, {"imageRevision", imageRevision}});
}
void Controller::addAnnotation(const QVariantMap &annotation) { command({{"type", "annotation"}, {"annotation", QJsonObject::fromVariantMap(annotation)}}); }
void Controller::undoAnnotation() { command({{"type", "undo"}}); }
void Controller::acceptProposal() {
    command({{"type", "accept"}, {"proposalId", m_states[m_projectId]["proposal"].toObject()["id"]}});
}
void Controller::renameAgent(const QString &name) { command({{"type", "agentName"}, {"name", name}}); }
void Controller::cancelAgent() { command({{"type", "cancel"}}); }

void Controller::startPreview() {
    if (!embeddingSupported() || m_projectId.isEmpty() || previewRunning()) return;
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("WAYLAND_DISPLAY", socketName());
    env.insert("QT_QPA_PLATFORM", "wayland");
    env.insert("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1");
    // Shared-memory buffers support software rendering on entry-level hardware.
    if (qEnvironmentVariable("QT_QUICK_BACKEND") == "software") env.insert("QT_WAYLAND_CLIENT_BUFFER_INTEGRATION", "shm");
    m_preview.setProcessEnvironment(env);
    const auto path = m_session.root() + "/projects/" + m_projectId;
    m_preview.setWorkingDirectory(path);
    const auto executable = qEnvironmentVariable("CENTAUR_PREVIEW", QCoreApplication::applicationDirPath() + "/centaur-preview");
    m_preview.start(executable, {path + "/App.qml"});
    emit previewChanged();
}
void Controller::stopPreview() {
    m_stopping = true;
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
    return m_session.root() + "/projects/" + m_projectId + "/.centaur/context-"
        + QUuid::createUuid().toString(QUuid::WithoutBraces) + ".png";
}
void Controller::revealProject() {
    if (!m_projectId.isEmpty()) QDesktopServices::openUrl(QUrl::fromLocalFile(m_session.root() + "/projects/" + m_projectId));
}
