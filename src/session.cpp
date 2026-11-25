#include "session.h"
#include "attachments.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QFileInfo>
#include <QFile>
#include <QDir>
#include <QUuid>
#include <QElapsedTimer>
#include <QThread>
#include <QPointer>
#include <QSettings>
#include <QScopeGuard>
#include <QDateTime>
#include <QRegularExpression>

static QString uid() { return QUuid::createUuid().toString(QUuid::WithoutBraces); }
static QJsonObject participantProfile(const QJsonObject &sharing, const QString &id) {
    for (const auto &entry : sharing["participants"].toArray()) {
        const auto person = entry.toObject();
        if (person["id"] == id) return person;
    }
    return {};
}
static QString runner(bool gtk = false) {
    if (gtk) return qEnvironmentVariable("CENTAUR_GTK_RUNNER", QCoreApplication::applicationDirPath() + "/centaur-gtk4-preview");
    return qEnvironmentVariable("CENTAUR_PREVIEW", QCoreApplication::applicationDirPath() + "/centaur-preview");
}

static QString proposalSource(const QJsonObject &proposal) {
    return proposal["gtk"].isObject() ? QString::fromUtf8(QJsonDocument(proposal["gtk"].toObject()).toJson(QJsonDocument::Compact)) : proposal["qml"].toString();
}
static bool isConflict(const QJsonObject &state) { return state["proposal"].toObject()["conflict"].isObject(); }

static void recordConflictOutcome(QJsonObject &state, const QJsonObject &proposal, const QString &outcome) {
    if (!proposal["conflict"].isObject()) return;
    auto messages = state["messages"].toArray();
    for (qsizetype i = messages.size(); i > 0; --i) {
        auto message = messages.at(i - 1).toObject();
        if (message["conflictId"] != proposal["id"]) continue;
        message["conflictOutcome"] = outcome;
        messages.replace(i - 1, message);
        state["messages"] = messages;
        return;
    }
}

static void removeConflictRequests(QJsonObject &state, const QJsonObject &proposal) {
    const auto choices = proposal["choices"].toObject();
    QJsonArray queue;
    for (const auto &value : state["agentQueue"].toArray()) {
        const auto request = value.toObject();
        if (!choices.contains(request["id"].toString()) && request["resolution"] != proposal["id"]) queue.append(value);
    }
    state["agentQueue"] = queue;
}

static const QString splitVoteOutcome = QStringLiteral("Neither side could agree, so no changes have been made to the app.");

static bool endSplitVote(QJsonObject &state, const QJsonObject &proposal) {
    QSet<QString> options;
    const auto votes = proposal["votes"].toObject();
    for (const auto &value : votes) options.insert(value.toString());
    if (options.size() < 2) return false;
    removeConflictRequests(state, proposal);
    auto directions = state["directions"].toObject();
    for (const auto &voter : proposal["voters"].toObject().keys()) directions.remove(voter);
    state["directions"] = directions;
    state["epoch"] = state["epoch"].toInt() + 1;
    state["proposal"] = QJsonObject();
    recordConflictOutcome(state, proposal, splitVoteOutcome);
    return true;
}

Session::Session(const QString &root, QObject *parent, int agentDeadlineMs) : QObject(parent), m_workspace(root), m_agent(nullptr,agentDeadlineMs) {
    m_updateToken = qEnvironmentVariable("CENTAUR_UPDATE_STARTING");
    m_socketName = "centaur-" + QString::fromLatin1(QCryptographicHash::hash(
        QFileInfo(root).absoluteFilePath().toUtf8(), QCryptographicHash::Sha256).toHex().left(24));
    connect(&m_server, &QLocalServer::newConnection, this, &Session::acceptConnection);
    connect(&m_client, &QLocalSocket::readyRead, this, [this] { read(&m_client); });
    connect(&m_client, &QLocalSocket::connected, this, [this] { m_starting = false; m_reconnect.stop(); emit connectionChanged(); });
    connect(&m_client, &QLocalSocket::disconnected, this, [this] {
        if (!m_starting) { m_reconnect.start(); emit connectionChanged(); }
    });
    m_reconnect.setInterval(1000);
    connect(&m_reconnect, &QTimer::timeout, this, [this] {
        if (m_client.state() == QLocalSocket::UnconnectedState) m_client.connectToServer(m_socketName);
    });
    connect(&m_agent, &Agent::resultReady, this, [this](const QString &run,const QJsonObject &reply) {
        if (run==m_expectedAgentRun && !m_agentProject.isEmpty()) finishAgent(reply);
    });
    connect(&m_agent, &Agent::failureReady, this, [this](const QString &run,const QString &message,const QJsonObject &) {
        if (run==m_expectedAgentRun && !m_agentProject.isEmpty()) agentError(message);
    });
    connect(&m_agent, &Agent::progress, this, [this](const QJsonObject &event) {
        if (m_agentProject.isEmpty() || event["runId"]!=m_expectedAgentRun) return;
        advanceActivity(m_agentProject,event["phase"].toString(),event);
    });
    connect(&m_agent, &Agent::idle, this, [this] { publish(); QTimer::singleShot(0, this, &Session::nextRequest); });
    connect(&m_agent, &Agent::modelReported, this, [this](const QString &model) {
        if (m_agentProject.isEmpty()) return;
        auto state = m_workspace.load(m_agentProject);
        if (state["agentModel"] == model) return;
        state["agentModel"] = model;
        if (persist(m_agentProject, state)) publish(m_agentProject);
    });
    connect(&m_validator, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        if (error != QProcess::FailedToStart) return;
        auto state = m_workspace.load(m_validatingProject);
        recordConflictOutcome(state, state["proposal"].toObject(), "The agreed change could not be checked. The app is unchanged.");
        state["proposal"] = QJsonObject();
        addMessage(state, state["agentName"].toString(), "Could not start the native app checker. Your app is unchanged.", "system");
        persist(m_validatingProject, state);
        m_validatingProject.clear();
        endActivity(state["id"].toString());
        state.remove("activeRequest"); persist(state["id"].toString(), state);
        publish();
        QTimer::singleShot(0, this, &Session::nextRequest);
    });
    connect(&m_validator, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
        [this](int code, QProcess::ExitStatus status) {
            const auto id = m_validatingProject;
            if (id.isEmpty()) { QTimer::singleShot(0, this, &Session::nextRequest); return; }
            m_validatingProject.clear();
            endActivity(id);
            auto state = m_workspace.load(id);
            QString error;
            state.remove("activeRequest");
            if (state["epoch"].toInt() != m_validatingEpoch) {
                retryRequest(state);
                addMessage(state, state["agentName"].toString(), "New directions arrived during the app check. I’m updating the request.", "system");
                state["proposal"] = QJsonObject();
            } else if (code != 0 || status != QProcess::NormalExit) {
                // QML diagnostics are local source errors, not provider credentials.
                auto detail = QString::fromUtf8(m_validator.readAllStandardError()).right(1500);
                detail.replace(m_workspace.projectPath(id), "[project]");
                addMessage(state, state["agentName"].toString(), "The proposed app did not pass its native check. Your current app is still running.\n" + detail, "system");
                recordConflictOutcome(state, state["proposal"].toObject(), "The agreed change failed its app check. The app is unchanged.");
                state["proposal"] = QJsonObject();
            } else {
                const auto proposal = state["proposal"].toObject();
                const auto archivePath = m_workspace.projectPath(id) + "/.centaur/annotations-v"
                    + QString::number(state["revision"].toInt()) + ".json";
                if (!Workspace::writeFile(archivePath, QJsonDocument(state["annotations"].toArray()).toJson(), &error)) {
                    addMessage(state, state["agentName"].toString(), "Could not preserve the current sketch: " + error, "system");
                    recordConflictOutcome(state, proposal, "The agreed change could not be saved. The app is unchanged.");
                    state["proposal"] = QJsonObject();
                } else if (m_workspace.applySource(id, proposalSource(proposal), proposal["message"].toString(), &error)) {
                    state["revision"] = state["revision"].toInt() + 1;
                    auto decisions = state["decisions"].toArray();
                    decisions.append(QJsonObject{{"summary", proposal["message"]}, {"authors", proposal["accepted"]},
                        {"requestedBy", proposal["requestedBy"]}, {"conflict", proposal["conflict"]},
                        {"restoredFrom", proposal["checkpoint"]},
                        {"revision", state["revision"]}, {"time", Workspace::now()}});
                    state["decisions"] = decisions;
                    state["contributors"] = QJsonArray();
                    state["annotations"] = QJsonArray();
                    state.remove("humanPointer");
                    state.remove("directions");
                    const auto original = proposal["choices"].toObject()[proposal["selected"].toString()].toObject();
                    const QString choice = original.isEmpty() ? QString("the Agent's suggestion")
                        : original["displayAuthor"].toString(original["author"].toString()) + "’s request";
                    const QString result = proposal["kind"] == "restore" ? " That version of the app was restored." : " The app was updated.";
                    recordConflictOutcome(state, proposal, "Agreed on " + choice + "." + result);
                    state["proposal"] = QJsonObject();
                    state.remove("creationPending");
                    auto imported=state.value("import").toObject();
                    if (!imported.isEmpty()) { imported["previewReady"]=true; imported["status"]="ready"; state["import"]=imported; }
                    if (!proposal["conflict"].isObject() || proposal["inlineConflict"] != true)
                        addMessage(state, state["agentName"].toString(), proposal["kind"] == "restore"
                            ? "Restored that version of the app." : "Updated the app.", "agent");
                    emit sourceChanged(id);
                } else {
                    addMessage(state, state["agentName"].toString(), "Could not save the change: " + error, "system");
                    recordConflictOutcome(state, proposal, "The agreed change could not be saved. The app is unchanged.");
                    state["proposal"] = QJsonObject();
                }
            }
            persist(id, state);
            publish(id);
            QTimer::singleShot(0, this, &Session::nextRequest);
        });
}

Session::~Session() {
    for (auto *process : m_imports) {
        disconnect(process,nullptr,this,nullptr); process->terminate();
        if (!process->waitForFinished(2000)) { process->kill(); process->waitForFinished(1000); }
    }
    disconnect(&m_agent, nullptr, this, nullptr);
    disconnect(&m_validator, nullptr, this, nullptr);
    m_agent.cancel();
    if (m_validator.state() != QProcess::NotRunning) { m_validator.kill(); m_validator.waitForFinished(1000); }
    // Socket destruction emits disconnected. Tear these connections down while
    // the peer/buffer containers are still alive, before member destruction.
    disconnect(&m_client, nullptr, this, nullptr);
    m_client.abort();
    for (auto *peer : m_peers) {
        disconnect(peer, nullptr, this, nullptr);
        peer->abort();
        peer->deleteLater();
    }
    m_peers.clear();
    m_buffers.clear();
    disconnect(&m_server, nullptr, this, nullptr);
    if (m_host) m_server.close();
}

void Session::start(bool background) {
    if (background) {
        m_client.connectToServer(m_socketName);
        if (m_client.waitForConnected(100)) return;
        m_client.abort();
        QProcess host;
        host.setProgram(qEnvironmentVariable("CENTAUR_HOST", QCoreApplication::applicationDirPath() + "/centaur-host"));
        host.setArguments({"--data-dir", m_workspace.root()});
        host.setStandardOutputFile(QProcess::nullDevice()); host.setStandardErrorFile(QProcess::nullDevice());
        if (!host.startDetached()) { emit error("Could not start the Centaur background host."); return; }
        QElapsedTimer timer; timer.start();
        while (timer.elapsed() < 5000) {
            m_client.connectToServer(m_socketName);
            if (m_client.waitForConnected(100)) return;
            m_client.abort(); QThread::msleep(50);
        }
        emit error("Could not connect to the Centaur background host. Check its installation.");
        return;
    }
    qunsetenv("CENTAUR_UPDATE_STARTING");
    m_lock = std::make_unique<QLockFile>(m_workspace.root() + "/session.lock");
    // QLockFile detects a dead host; never unlink a live host's socket.
    if (m_lock->tryLock(0)) {
        QLocalServer::removeServer(m_socketName);
        m_server.setSocketOptions(QLocalServer::UserAccessOption);
        if (!m_server.listen(m_socketName)) { emit error(m_server.errorString()); return; }
        m_host = true;
        m_starting = false;
        m_network = std::make_unique<CollaborationHost>(m_workspace.root());
        m_network->setUpdating(!m_updateToken.isEmpty());
        connect(m_network.get(), &CollaborationHost::membershipChanged, this, [this] { publish(); });
        connect(m_network.get(), &CollaborationHost::command, this, [this](const QJsonObject &command, QIODevice *sender) { handle(command, sender); });
        for (const auto &project : m_workspace.projects()) {
            const auto id = project.toMap()["id"].toString();
            auto state = m_workspace.load(id);
            auto imported = state.value("import").toObject();
            auto importLocal=state["importLocal"].toObject();
            if (!imported.isEmpty() && !importLocal.contains("sourceAvailable")) {
                const auto source=m_workspace.projectPath(id)+"/.centaur/import/"+imported["storage"].toString()+"/source";
                importLocal["sourceAvailable"]=QFileInfo(source).isDir() && !QFileInfo(source).isSymLink();
                state["importLocal"]=importLocal; persist(id,state);
            }
            if (imported["status"] == "fetching" || imported["status"] == "inspecting") {
                importLocal.remove("pending"); importLocal.remove("currentTool");
                auto diagnostics=importLocal["diagnostics"].toObject();
                diagnostics["failure"]=QJsonObject{{"schemaVersion",1},{"category","interrupted"},{"code","interrupted"},
                    {"retryable",false},{"sourceAvailable",importLocal["sourceAvailable"]}};
                importLocal["diagnostics"]=diagnostics; state["importLocal"]=importLocal;
                imported["status"] = "interrupted"; state["import"] = imported;
                addMessage(state,state["agentName"].toString(),"The source import was interrupted. Retry when you’re ready; the original is untouched.","system");
                persist(id,state);
            }
            if (!state["activeRequest"].toObject().isEmpty()) {
                auto queue = state["agentQueue"].toArray(); queue.prepend(state["activeRequest"]);
                state["agentQueue"] = queue; state.remove("activeRequest"); persist(id, state);
            }
            auto proposal = state["proposal"].toObject();
            if (proposal.value("conflict").isObject() && !proposal.contains("voters") && !m_network->sharing(id)["enabled"].toBool()) {
                QJsonObject voters, votes;
                for (const auto &value : proposal["authors"].toArray()) {
                    const auto name = value.toString();
                    if (name.isEmpty()) continue;
                    const auto participant = "local:" + name;
                    voters[participant] = name;
                    if (proposal["accepted"].toArray().contains(value)) votes[participant] = "compromise";
                }
                proposal["voters"] = voters;
                proposal["votes"] = votes;
                state["proposal"] = proposal;
                persist(id, state);
            }
            // Do not auto-apply proposals made under the old everyone-agrees
            // policy, or resume an interrupted automatic check without context.
            if (!proposal.isEmpty() && (!proposal["conflict"].isObject()
                || proposal["voters"].toObject().size() < 2 || proposal["resolving"].toBool())) {
                if (proposal["conflict"].isObject()) removeConflictRequests(state, proposal);
                recordConflictOutcome(state, proposal, "The vote was interrupted. The app is unchanged.");
                state["proposal"] = QJsonObject();
                addMessage(state, state["agentName"].toString(), state["agentQueue"].toArray().isEmpty() ? "An unfinished change wasn't applied. Ask me again to continue." : "An interrupted change is queued to continue.", "system");
                persist(id, state);
            } else if (proposal["conflict"].isObject() && endSplitVote(state, proposal)) {
                if (proposal["inlineConflict"] != true) addMessage(state, state["agentName"].toString(), splitVoteOutcome, "system");
                persist(id, state);
            }
        }
        publish();
        QTimer::singleShot(0, this, &Session::nextRequest);
    } else {
        m_client.connectToServer(m_socketName);
        if (!m_client.waitForConnected(1500)) emit error("Could not join the local project host. Close and reopen Centaur.");
    }
}

void Session::acceptConnection() {
    while (m_server.hasPendingConnections()) {
        auto *peer = m_server.nextPendingConnection();
        m_peers.insert(peer);
        connect(peer, &QLocalSocket::readyRead, this, [this, peer] { read(peer); });
        connect(peer, &QLocalSocket::disconnected, this, [this, peer] {
            m_peers.remove(peer); m_buffers.remove(peer); peer->deleteLater();
            publish(); // Refresh the updater's other-window gate immediately.
        });
        publish();
    }
}

void Session::reply(QIODevice *socket, const QJsonObject &data) {
    if (socket) socket->write(QJsonDocument(data).toJson(QJsonDocument::Compact) + '\n');
    else if (data["type"] == "error") emit error(data["message"].toString());
    else if (data["type"] == "annotationRejected") emit annotationRejected(data["annotationId"].toString(), data["message"].toString());
    else emit snapshot(data);
}

void Session::read(QLocalSocket *socket) {
    m_buffers[socket] += socket->readAll();
    if (m_buffers[socket].size() > 8 * 1024 * 1024) { socket->abort(); return; }
    while (m_buffers[socket].contains('\n')) {
        const auto index = m_buffers[socket].indexOf('\n');
        const auto line = m_buffers[socket].left(index);
        m_buffers[socket].remove(0, index + 1);
        const auto data = QJsonDocument::fromJson(line).object();
        if (m_host) handle(data, socket);
        else if (data["type"] == "error") emit error(data["message"].toString());
        else if (data["type"] == "annotationRejected") emit annotationRejected(data["annotationId"].toString(), data["message"].toString());
        else emit snapshot(data);
    }
}

void Session::send(QJsonObject command) {
    if (m_host) handle(command);
    else if (m_client.state() == QLocalSocket::ConnectedState) reply(&m_client, command);
    else emit error("The local project host is unavailable.");
}

void Session::publish(const QString &id) {
    QJsonArray states;
    for (const auto &project : m_workspace.projects()) {
        auto state = m_workspace.load(project.toMap()["id"].toString());
        state["sharing"] = m_network ? m_network->sharing(state["id"].toString()) : QJsonObject();
        state["queueCount"] = state["agentQueue"].toArray().size();
        state.remove("networkAcks"); state.remove("agentQueue"); state.remove("activeRequest");
        state.remove("importLocal");
        state.remove("directions");
        state.remove("agentActivity");
        if (m_activities.contains(state["id"].toString())) state["agentActivity"]=m_activities.value(state["id"].toString());
        states.append(state);
    }
    QJsonObject data{{"type", "snapshot"}, {"projects", QJsonArray::fromVariantList(m_workspace.projects())},
        {"states", states}, {"agentAvailable", m_agent.available()}, {"agentExecutable", m_agent.executable()},
        {"busyProject", m_agent.busy() ? m_agentProject : m_validatingProject}, {"changedProject", id},
        {"updateBlocked", updateBlocked()}, {"updateHeld", !m_updateToken.isEmpty()}, {"localWindows", m_peers.size()}};
    emit snapshot(data);
    for (auto *peer : m_peers) reply(peer, data);
    if (m_network) m_network->publish(data);
}

void Session::addMessage(QJsonObject &state, const QString &author, const QString &text, const QString &kind,
                         const QJsonObject &comment, const QString &participant, const QString &conflictId, const QJsonArray &attachments, const QString &clientId) {
    auto messages = state["messages"].toArray();
    QJsonObject message{{"id", uid()}, {"author", author}, {"text", text}, {"kind", kind},
        {"time", Workspace::now()}, {"revision", state["revision"]}};
    if (!QUuid(clientId).isNull()) message["clientId"]=QUuid(clientId).toString(QUuid::WithoutBraces);
    if (!attachments.isEmpty()) message["attachments"]=attachments;
    if (!comment.isEmpty()) message["comment"] = comment;
    if (!participant.isEmpty()) {
        message["participant"] = participant;
        const auto person = participantProfile(m_network->sharing(state["id"].toString()), participant);
        if (person.contains("displayName")) message["displayAuthor"] = person["displayName"];
        if (person.contains("profileId")) message["profileId"] = person["profileId"];
    }
    if (!conflictId.isEmpty()) message["conflictId"] = conflictId;
    messages.append(message);
    QFile history(m_workspace.projectPath(state["id"].toString()) + "/.centaur/conversation.jsonl");
    if (history.open(QIODevice::WriteOnly | QIODevice::Append))
        history.write(QJsonDocument(message).toJson(QJsonDocument::Compact) + '\n');
    // Bound live state and model context on modest hardware.
    const auto activeConflict = state["proposal"].toObject()["id"].toString();
    while (messages.size() > 250) {
        const auto first = messages.first().toObject();
        messages.removeAt(!activeConflict.isEmpty() && first["conflictId"] == activeConflict ? 1 : 0);
    }
    state["messages"] = messages;
}

bool Session::persist(const QString &id, QJsonObject state) {
    state["updated"] = Workspace::now();
    QString error;
    if (m_workspace.save(id, state, &error)) return true;
    emit this->error("Could not save the project: " + error);
    return false;
}

bool Session::updateBlocked() const {
    if (!m_imports.isEmpty() || m_agent.busy() || !m_validatingProject.isEmpty() || m_validator.state() != QProcess::NotRunning
        || (m_network && m_network->preparingInvitation())) return true;
    for (const auto &project : m_workspace.projects()) {
        const auto state = m_workspace.load(project.toMap()["id"].toString());
        if (!state["agentQueue"].toArray().isEmpty()) return true;
    }
    return false;
}

void Session::handle(const QJsonObject &command, QIODevice *sender) {
    const auto type = command["type"].toString();
    const auto strokeId = type == "annotation" ? command["annotation"].toObject()["id"].toString().left(36) : QString();
    auto fail = [this, sender, strokeId](const QString &message) {
        reply(sender, {{"type", strokeId.isEmpty() ? "error" : "annotationRejected"}, {"message", message}, {"annotationId", strokeId}});
    };
    if (type == "ownerDisplayName") {
        const auto name = command["name"].toString().trimmed().left(50);
        if ((!sender || m_peers.contains(qobject_cast<QLocalSocket *>(sender))) && m_network && !name.isEmpty()
                && !m_network->setOwnerDisplayName(name)) fail("Could not save your shared profile name.");
        return;
    }
    if (type == "refreshAvatar") {
        if ((!sender || m_peers.contains(qobject_cast<QLocalSocket *>(sender))) && m_network) m_network->refreshAvatar();
        return;
    }
    if (type == "shutdownIfIdle" || type == "finishUpdate") {
        // Maintenance is restricted to the per-user LOCAL socket, never TLS peers.
        auto *local = qobject_cast<QLocalSocket *>(sender);
        if (!local || !m_peers.contains(local)) { fail("Updates require a local connection."); return; }
        if (!m_updateToken.isEmpty() && command["token"].toString() != m_updateToken) {
            fail("Another update is starting Centaur."); return;
        }
        if (type == "finishUpdate") {
            if (m_updateToken.isEmpty()) { fail("No update is waiting."); return; }
            m_updateToken.clear(); if (m_network) m_network->setUpdating(false);
            reply(sender, {{"type", "updateResumed"}}); publish();
            QTimer::singleShot(0, this, &Session::nextRequest); return;
        }
        if (updateBlocked() || (m_peers.size() > 1 && m_updateToken.isEmpty())) {
            fail("Centaur is busy or another window is open. Finish its work and try again."); return;
        }
        m_updateStopping = true;
        if (m_network) m_network->setUpdating(true);
        reply(sender, {{"type", "updateStopping"}});
        QTimer::singleShot(100, QCoreApplication::instance(), &QCoreApplication::quit); return;
    }
    if (m_updateStopping || !m_updateToken.isEmpty()) { fail("Centaur is restarting for an update. Try again shortly."); return; }
    if (importCommand(command,sender)) return;
    if (type == "shutdown") { QTimer::singleShot(100, QCoreApplication::instance(), &QCoreApplication::quit); return; }
    if (type == "resolveEndedShare") {
        if (sender && !m_peers.contains(qobject_cast<QLocalSocket *>(sender))) { fail("This choice requires a local connection."); return; }
        QString copyId, error;
        if (!m_workspace.resolveEndedShare(command["projectId"].toString(), command["retain"].toBool(), &copyId, &error)) {
            fail(error); return;
        }
        publish(copyId);
        if (!copyId.isEmpty()) reply(sender, {{"type", "created"}, {"projectId", copyId}});
        return;
    }
    if (type == "create" || type == "openStarter") {
        // Only the host has the authoritative list at startup. Resolve this in
        // one command so joining windows cannot each create a starter project.
        const bool starter = type == "openStarter";
        const auto projects = starter ? m_workspace.projects() : QVariantList();
        QString error;
        const auto id = !projects.isEmpty() ? projects.first().toMap()["id"].toString()
            : m_workspace.createProject(starter ? "Family board" : command["name"].toString(),
                starter ? "A little space for everyday things, made together." : command["description"].toString(), &error, command["appFormat"].toString());
        if (id.isEmpty()) { fail(error); return; }
        const auto prompt=command["appFormat"]=="gtk4-v1" ? command["createPrompt"].toString().trimmed().left(12000) : QString();
        if (!prompt.isEmpty()) {
            auto state=m_workspace.load(id); state["creationPending"]=true;
            if (!persist(id,state)) return;
        }
        publish(id);
        reply(sender, {{"type", starter ? "opened" : "created"}, {"projectId", id}});
        if (!prompt.isEmpty()) {
            // Use the normal addressed-message path: persisted conversation,
            // bounded agent execution, validation, conflict policy and retries.
            handle({{"type","message"},{"projectId",id},{"author",command["author"]},
                {"text","@"+m_workspace.load(id)["agentName"].toString()+" "+prompt}},sender);
        }
        return;
    }
    const auto id = command["projectId"].toString();
    auto state = m_workspace.load(id);
    if (state.isEmpty()) { fail("That project is unavailable."); return; }
    const auto sharing = m_network->sharing(id);
    const auto localName = command["author"].toString().trimmed().left(50);
    const auto author = !qobject_cast<QSslSocket *>(sender) && sharing["enabled"].toBool()
        ? sharing["owner"].toString(localName) : localName;
    const bool shared = sharing["enabled"].toBool();
    const auto participant = qobject_cast<QSslSocket *>(sender) ? command["_memberId"].toString()
        : shared ? QString("host") : "local:" + author;
    const auto displayName = participantProfile(sharing, participant)["displayName"].toString(author);
    if (author.isEmpty()) { fail("Choose your name before contributing."); return; }
    if (!command["_memberId"].toString().isEmpty()) {
        auto acks = state["networkAcks"].toObject();
        acks[command["_memberId"].toString()] = command["sequence"]; state["networkAcks"] = acks;
    }
    if (type == "invite" || type == "stopSharing") {
        QString error;
        if (type == "invite") {
            if (command["address"] == "iroh") {
                const QPointer<QIODevice> recipient(sender);
                const bool local = sender == nullptr;
                m_network->inviteInternet(id, author, [this, recipient, local, id](const QString &code, const QString &error) {
                    if (!local && !recipient) return;
                    reply(recipient, code.isEmpty() ? QJsonObject{{"type", "error"}, {"message", error}}
                                                   : QJsonObject{{"type", "invitation"}, {"projectId", id}, {"code", code}});
                    publish(id);
                });
                return;
            }
            const auto code = m_network->invite(id, author, command["address"].toString(), &error);
            if (code.isEmpty()) { fail(error); return; }
            reply(sender, {{"type", "invitation"}, {"projectId", id}, {"code", code}});
        } else if (!m_network->stopSharing(id, &error)) { fail(error); return; }
    } else if (type == "message") {
        const auto text = command["text"].toString().trimmed().left(12000);
        QJsonArray attachments;
        QString attachmentError;
        if (!Attachments::prepare(m_workspace.projectPath(id),command.value("attachments"),attachments,attachmentError)) {
            fail(attachmentError); return;
        }
        if (text.isEmpty() && attachments.isEmpty()) return;
        auto comment = command["comment"].toObject();
        if (!comment.isEmpty()) {
            if (comment["revision"] != state["revision"]) { fail("The app changed before that comment arrived. Place its pointer again on the current app."); return; }
            const auto point = comment["point"].toObject(); const auto frame = comment["frame"].toObject();
            QJsonObject cleanPoint, cleanFrame;
            for (const auto &key : {"x", "y"})
                if (point[key].isDouble() && point[key].toDouble() >= 0 && point[key].toDouble() <= 1) cleanPoint[key] = point[key];
            for (const auto &key : {"x", "y", "width", "height"})
                if (frame[key].isDouble() && frame[key].toDouble() >= 0 && frame[key].toDouble() <= 1) cleanFrame[key] = frame[key];
            if (cleanPoint.size() != 2 || cleanFrame.size() != 4 || cleanFrame["width"].toDouble() <= 0 || cleanFrame["height"].toDouble() <= 0) {
                fail("That comment's canvas location is invalid. Place its pointer again."); return;
            }
            comment = {{"point", cleanPoint}, {"frame", cleanFrame}, {"revision", state["revision"]}};
        }
        addMessage(state, author, text, "human", comment, participant, {},attachments,command["clientId"].toString());
        auto contributors = state["contributors"].toArray();
        if (!contributors.contains(author)) contributors.append(author);
        state["contributors"] = contributors;
        if (correctImportBranch(id,state,text,author)) return;
        const auto imported = state.value("import").toObject();
        const bool importAnswer = !imported.isEmpty() && !imported["previewReady"].toBool()
            && (imported["status"] == "awaitingAnswer" || imported["status"] == "investigating"
                || imported["status"] == "failed" || imported["status"] == "interrupted");
        const QRegularExpression mention("(?<![\\w@])@" + QRegularExpression::escape(state["agentName"].toString("centaur")) + "(?![\\w-])",
            QRegularExpression::CaseInsensitiveOption | QRegularExpression::UseUnicodePropertiesOption);
        const bool addressed = importAnswer || mention.match(text).hasMatch();
        if (!addressed && sharing["participants"].toArray().size() >= 2) {
            const auto pointer = state["humanPointer"].toObject();
            if (pointer.isEmpty() || pointer["participant"] != participant) {
                state.remove("humanPointer");
                if (!comment.isEmpty()) {
                    comment["messageId"] = state["messages"].toArray().last().toObject()["id"];
                    comment["participant"] = participant;
                    for (const auto &value : sharing["participants"].toArray()) {
                        const auto person = value.toObject();
                        if (person["id"] == participant) { comment["color"] = person["color"]; break; }
                    }
                    state["humanPointer"] = comment;
                }
            }
        }
        if (addressed || (!shared && isConflict(state))) {
            if (isConflict(state)) {
                const auto proposal = state["proposal"].toObject();
                removeConflictRequests(state, proposal);
                recordConflictOutcome(state, proposal, "New directions superseded this vote. The app is unchanged.");
            }
            state["epoch"] = state["epoch"].toInt() + 1; state["proposal"] = QJsonObject();
        }
        if (addressed) {
            if (!imported.isEmpty()) {
                auto info=imported; info["inspectionRounds"]=0;
                auto local=state["importLocal"].toObject(); local.remove("seenTools"); local["failureRounds"]=0;
                local["toolCount"]=0; state["importLocal"]=local;
                if (importAnswer) info["status"]="investigating";
                state["import"]=info;
            }
            auto queue = state["agentQueue"].toArray();
            if (queue.size() >= 50) { fail("The request queue is full. Wait for the agent to catch up."); return; }
            QString image;
            const auto filename = command["image"].toString();
            const auto expected = m_workspace.projectPath(id) + "/.centaur/";
            const auto canonical = QFileInfo(filename).canonicalFilePath();
            if (canonical.startsWith(expected) && canonical.endsWith(".png") && command["imageRevision"] == state["revision"]) image = canonical;
            const auto messages = state["messages"].toArray();
            const auto context = Attachments::agentContext(messages, messages.size()-1, state["agentName"].toString("centaur"));
            const QJsonObject request{{"id", uid()}, {"author", author}, {"participant", participant}, {"text", text},
                {"messageId",messages.last().toObject()["id"]}, {"referenceMessage",context["referenceMessage"]},
                {"referenceAuthor",context["referenceAuthor"]}, {"attachments",context["attachments"]},
                {"image", image}, {"imageRevision", state["revision"]}, {"comment", comment}, {"import", importAnswer}};
            queue.append(request);
            state["agentQueue"] = queue;
            auto directions = state["directions"].toObject();
            directions[participant] = QJsonObject{{"id", request["id"]}, {"participant", participant},
                {"author", author}, {"displayAuthor", displayName}, {"text", text}, {"revision", state["revision"]}};
            state["directions"] = directions;
        }
        if (!persist(id, state)) return;
        nextRequest();
    } else if (type == "annotation") {
        if (command.contains("baseRevision") && command["baseRevision"] != state["revision"]) {
            fail("The app changed before that drawing arrived. Draw on the current app."); return;
        }
        const auto input = command["annotation"].toObject();
        const auto points = input["points"].toArray();
        if (points.isEmpty() || points.size() > 4096) { fail("That drawing is too large."); return; }
        if (input["tool"] != "draw" && input["tool"] != "comment") { fail("That drawing tool is unavailable."); return; }
        QJsonArray cleanPoints;
        for (const auto &value : points) {
            const auto point = value.toObject();
            if (!point["x"].isDouble() || !point["y"].isDouble()
                || point["x"].toDouble() < 0 || point["x"].toDouble() > 1
                || point["y"].toDouble() < 0 || point["y"].toDouble() > 1) { fail("That drawing has an invalid point."); return; }
            cleanPoints.append(QJsonObject{{"x", point["x"]}, {"y", point["y"]}});
        }
        QJsonObject annotation{{"tool", input["tool"]}, {"points", cleanPoints}};
        const auto frame = input["frame"].toObject(); QJsonObject cleanFrame;
        for (const auto &key : {"x", "y", "width", "height"}) if (frame[key].isDouble() && frame[key].toDouble() >= 0 && frame[key].toDouble() <= 1) cleanFrame[key] = frame[key];
        if (cleanFrame.size() == 4) annotation["frame"] = cleanFrame;
        auto annotations = state["annotations"].toArray();
        const bool suppliedId = !QUuid(strokeId).isNull() && strokeId.size() == 36;
        if (suppliedId) for (const auto &mark : annotations) {
            if (mark.toObject()["id"] != strokeId) continue;
            if (mark.toObject()["participant"] != participant) fail("That drawing identifier is already in use.");
            return;
        }
        int pointCount = points.size();
        for (const auto &mark : annotations) pointCount += mark.toObject()["points"].toArray().size();
        if (annotations.size() >= 100 || pointCount > 16384) { fail("This canvas is full. Undo some marks or build this change before adding more."); return; }
        annotation["id"] = suppliedId ? strokeId : uid(); annotation["author"] = author; annotation["participant"] = participant;
        auto colour = input["color"].toString();
        static const QRegularExpression hexColour("^#[0-9a-fA-F]{6}$");
        if (!hexColour.match(colour).hasMatch()) {
            colour = "#138EF5";
            for (const auto &value : sharing["participants"].toArray()) {
                const auto member = value.toObject();
                if (member["id"] == participant) colour = member["color"].toString(colour);
            }
        }
        annotation["color"] = colour;
        annotation["revision"] = state["revision"]; annotation["time"] = Workspace::now();
        annotations.append(annotation);
        state["annotations"] = annotations;
        if (!isConflict(state)) { state["epoch"] = state["epoch"].toInt() + 1; state["proposal"] = QJsonObject(); }
        auto contributors = state["contributors"].toArray();
        if (!contributors.contains(author)) contributors.append(author);
        state["contributors"] = contributors;
        if (!persist(id, state)) { fail("Could not save the drawing. Please try again."); return; }
    } else if (type == "undo") {
        auto annotations = state["annotations"].toArray();
        for (int i = annotations.size() - 1; i >= 0; --i) {
            const auto mark = annotations[i].toObject();
            const auto writer = mark["participant"].toString();
            bool own = writer == participant || (writer.isEmpty() && !shared && mark["author"] == author);
            if (participant == "host" && writer == "local:" + author) own = true;
            for (const auto &value : sharing["participants"].toArray()) {
                const auto person = value.toObject();
                if (person["id"] == participant && person["previousIds"].toArray().contains(writer)) own = true;
            }
            if (own && mark["revision"] == state["revision"]) {
                annotations.removeAt(i); break;
            }
        }
        state["annotations"] = annotations;
        if (!isConflict(state)) { state["epoch"] = state["epoch"].toInt() + 1; state["proposal"] = QJsonObject(); }
        persist(id, state);
    } else if (type == "accept" || type == "rejectProposal") {
        auto proposal = state["proposal"].toObject();
        if (proposal.isEmpty() || proposal["id"] != command["proposalId"]
            || proposal["epoch"] != state["epoch"]) { fail("That proposal has changed. Review the latest one."); return; }
        if (!proposal["conflict"].isObject()) { fail("Only conflicting requests need agreement. Ask the agent to prepare this change again."); return; }
        if (proposal["resolving"].toBool() || m_validatingProject == id) { fail("This resolution is already being prepared."); return; }
        const auto voters = proposal["voters"].toObject();
        if (voters.size() < 2 || !voters.contains(participant)) { fail("Only the people whose requests conflict can decide this proposal."); return; }
        if (type == "rejectProposal") {
            removeConflictRequests(state, proposal);
            state["epoch"] = state["epoch"].toInt() + 1;
            state["proposal"] = QJsonObject();
            recordConflictOutcome(state, proposal, displayName + " declined the proposed resolution. The app stays as it is.");
            addMessage(state, state["agentName"].toString(), displayName + " declined the proposed resolution. The app stays as it is.", "system");
            if (persist(id, state)) { publish(id); QTimer::singleShot(0, this, &Session::nextRequest); }
            return;
        }
        const auto choice = command["choice"].toString("compromise");
        const auto option = choice.isEmpty() ? QString("compromise") : choice;
        const auto original = proposal["choices"].toObject().value(option).toObject();
        if (option != "compromise" && original.isEmpty()) { fail("That resolution is unavailable."); return; }
        auto votes = proposal["votes"].toObject();
        if (votes.contains(participant)) return;
        votes[participant] = option;
        proposal["votes"] = votes;
        if (endSplitVote(state, proposal)) {
            if (proposal["inlineConflict"] != true) addMessage(state, state["agentName"].toString(), splitVoteOutcome, "system");
            if (persist(id, state)) { publish(id); QTimer::singleShot(0, this, &Session::nextRequest); }
            return;
        }
        QJsonArray accepted;
        for (const auto &key : voters.keys()) if (votes[key] == option) accepted.append(voters[key]);
        proposal["accepted"] = accepted;
        const bool unanimous = accepted.size() == voters.size();
        if (unanimous) {
            removeConflictRequests(state, proposal);
            proposal["resolving"] = true;
            proposal["selected"] = option;
        }
        state["proposal"] = proposal;
        if (!persist(id, state)) return;
        if (unanimous) QTimer::singleShot(0, this, &Session::nextRequest);
    } else if (type == "agentName") {
        const auto name = command["name"].toString().trimmed().remove('@').left(30);
        if (name.isEmpty() || name.contains(' ')) { fail("Use a single name without spaces."); return; }
        state["agentName"] = name;
        persist(id, state);
    } else if (type == "rename") {
        const auto name = command["name"].toString().trimmed();
        if (name.isEmpty() || name.size() > 100) { fail("Give the project a name of up to 100 characters."); return; }
        state["name"] = name;
        if (!persist(id, state)) return;
    } else if (type == "delete") {
        if (m_imports.contains(id)) { fail("Wait for the source import to finish before deleting."); return; }
        if (m_agentProject == id && m_agent.busy()) { fail("Wait for the agent to finish before deleting."); return; }
        if (m_validatingProject == id) { fail("Wait for the app check to finish before deleting."); return; }
        QString error;
        if (!m_workspace.deleteProject(id, &error)) { fail(error); return; }
        if (m_network->sharing(id)["enabled"].toBool()) m_network->stopSharing(id, nullptr, true);
    } else if (type == "archive") {
        if (m_imports.contains(id)) { fail("Wait for the source import to finish before archiving."); return; }
        if (m_agentProject == id && m_agent.busy()) { fail("Wait for the agent to finish before archiving."); return; }
        if (m_validatingProject == id) { fail("Wait for the app check to finish before archiving."); return; }
        state["archived"] = true;
        if (persist(id, state) && m_network->sharing(id)["enabled"].toBool()) m_network->stopSharing(id, nullptr, true);
    } else if (type == "cancel") {
        if (m_imports.contains(id)) {
            auto *process=m_imports.value(id); process->terminate();
            QTimer::singleShot(2000,process,[process] { if (process->state()!=QProcess::NotRunning) process->kill(); });
        }
        if (m_agentProject == id && m_agent.busy()) {
            m_agent.cancel(); m_agentProject.clear(); m_agentAuthor.clear();
        }
        if (m_validatingProject == id) { m_validatingProject.clear(); m_validator.kill(); }
        endActivity(id);
        recordConflictOutcome(state, state["proposal"].toObject(), "The vote was cancelled. The app is unchanged.");
        state.remove("activeRequest"); state["agentQueue"] = QJsonArray(); state["proposal"] = QJsonObject();
        auto local=state["importLocal"].toObject(); local.remove("pending"); local.remove("currentTool"); state["importLocal"]=local;
        auto imported=state["import"].toObject();
        if (!imported.isEmpty() && !imported["previewReady"].toBool()) { imported["status"]="interrupted"; state["import"]=imported; }
        addMessage(state, state["agentName"].toString(), displayName + " stopped the agent. Pending requests were cleared.", "system");
        persist(id, state);
        QTimer::singleShot(0, this, &Session::nextRequest);
    }
    publish(id);
}

void Session::finishAgent(const QJsonObject &agentReply) {
    QTimer::singleShot(0, this, &Session::nextRequest);
    const auto id = m_agentProject;
    const auto settle=qScopeGuard([this,id] { settleActivity(id); });
    const auto requester = m_agentAuthor;
    auto state = m_workspace.load(id);
    auto reply=agentReply;
    if (reply["kind"]=="patch" && state["epoch"].toInt()==m_agentEpoch) {
        QString error;
        reply=state["appFormat"]=="gtk4-v1" ? Agent::resolvePatch(reply,m_workspace.source(id),&error) : QJsonObject();
        if (reply.isEmpty()) {
            agentError(error.isEmpty() ? "Focused changes are available only for an existing GTK app." : error,"coordinator_patch_invalid");
            return;
        }
    }
    m_agentProject.clear();
    m_agentAuthor.clear();
    bool automatic = false;
    QString conflictId;
    state.remove("activeRequest");
    const auto agreement = state["proposal"].toObject();
    const auto resolution = m_activeRequest.value("resolution").toString();
    if (!resolution.isEmpty()) {
        if (state["epoch"].toInt() != m_agentEpoch || agreement["id"] != resolution) {
            persist(id, state); publish(id); return;
        }
        state["proposal"] = QJsonObject();
        if (reply["conflict"].isObject() || (reply["kind"] != "proposal" && reply["kind"] != "restore")) {
            recordConflictOutcome(state, agreement, "The agreed request did not produce an app change.");
            addMessage(state, state["agentName"].toString(), reply["message"].toString() +
                " The agreed request did not produce an app change.", "agent");
            persist(id, state); publish(id); return;
        }
    }
    const bool sourceTool=reply["kind"]=="inspect" || reply["kind"]=="retry" || reply["kind"]=="artifact";
    if (!state.value("import").toObject().isEmpty() && (sourceTool || !state.value("import").toObject()["previewReady"].toBool())
        && state["epoch"].toInt() == m_agentEpoch) {
        auto info=state["import"].toObject();
        const auto kind=reply["kind"].toString();
        if (reply["conflict"].isObject()) {
            info["status"]="awaitingAnswer"; state["import"]=info;
            addMessage(state,state["agentName"].toString(),reply["message"].toString()+" Please resolve these directions together before I prepare the adaptation.","agent");
            persist(id,state); publish(id); return;
        }
        if (kind=="inspect" || kind=="retry") { importTool(id,state,reply,requester); return; }
        info["status"]="awaitingAnswer"; state["import"]=info;
        addMessage(state,state["agentName"].toString(),reply["message"].toString(),"agent");
        persist(id,state); publish(id);
        if (kind=="artifact") importJob(id,"stage",{{"files",reply["files"]},{"target",reply["target"]}});
        else if (kind=="proposal" && reply["gtk"].isObject()) importJob(id,"bundle",{{"bundle",reply["gtk"]}});
        return;
    }
    if (state["epoch"].toInt() != m_agentEpoch) {
        retryRequest(state);
        addMessage(state, state["agentName"].toString(), "New directions arrived. I’m checking the request against the latest conversation.", "system");
    } else {
        if (reply["kind"] == "proposal" || reply["kind"] == "restore") {
            auto proposal = reply;
            if (reply["kind"] == "proposal" && ((state["appFormat"] == "gtk4-v1") != reply["gtk"].isObject())) {
                addMessage(state, state["agentName"].toString(), "The agent returned the wrong app format. Your app is unchanged.", "system");
                persist(id, state); publish(id); return;
            }
            if (reply["kind"] == "restore") {
                QString error;
                const auto source = m_workspace.sourceAt(id, reply["checkpoint"].toString(), &error);
                if (source.isEmpty()) {
                    addMessage(state, state["agentName"].toString(), "Could not restore that saved app. Your app is unchanged. " + error, "system");
                    persist(id, state);
                    publish(id);
                    return;
                }
                // Restore the exact checkpoint, never model-supplied replacement source.
                if (state["appFormat"] == "gtk4-v1") proposal["gtk"] = QJsonDocument::fromJson(source.toUtf8()).object();
                else proposal["qml"] = source;
            } else proposal.remove("checkpoint");
            const auto conflict = reply["conflict"];
            QJsonArray authors{requester};
            if (conflict.isObject()) {
                authors = conflict.toObject()["authors"].toArray();
                QJsonObject voters, choices;
                const auto directions = state["directions"].toObject();
                const auto messages = state["messages"].toArray();
                const auto roster = m_network->sharing(id)["participants"].toArray();
                for (const auto &value : authors) {
                    const auto name = value.toString();
                    QString participant;
                    // Current requests and authenticated membership bind votes
                    // to people even when a display name changes on one device.
                    for (const auto &person : roster)
                        if (person.toObject()["name"] == name) participant = person.toObject()["id"].toString();
                    for (qsizetype i = messages.size(); participant.isEmpty() && i > 0; --i) {
                        const auto message = messages.at(i - 1).toObject();
                        if (message["kind"] == "human" && message["author"] == name) participant = message["participant"].toString();
                    }
                    if (!participant.isEmpty() && !voters.contains(participant)) {
                        voters[participant] = name;
                        const auto direction = directions.value(participant).toObject();
                        if (direction["revision"] == state["revision"]) choices[direction["id"].toString()] = direction;
                    }
                }
                if (voters.size() != authors.size() || voters.size() < 2) {
                    addMessage(state, state["agentName"].toString(), "I couldn't identify the people involved in that conflict. Please clarify whose requests differ and ask me again.", "system");
                    persist(id, state);
                    publish(id);
                    return;
                }
                proposal["voters"] = voters;
                proposal["choices"] = choices;
                proposal["votes"] = QJsonObject();
            }
            proposal["id"] = uid(); proposal["epoch"] = m_agentEpoch;
            proposal["requestedBy"] = requester;
            proposal["authors"] = authors;
            automatic = conflict.isNull();
            proposal["accepted"] = automatic ? QJsonArray{requester} : QJsonArray();
            if (!resolution.isEmpty()) {
                proposal["id"] = agreement["id"];
                proposal["authors"] = agreement["authors"];
                proposal["accepted"] = agreement["accepted"];
                proposal["conflict"] = agreement["conflict"];
                proposal["resolving"] = true;
                proposal["selected"] = agreement["selected"];
                proposal["choices"] = agreement["choices"];
                proposal["inlineConflict"] = agreement["inlineConflict"];
                proposal["voters"] = agreement["voters"];
                proposal["votes"] = agreement["votes"];
            } else if (conflict.isObject() && state["appFormat"] == "gtk4-v1") {
                conflictId = proposal["id"].toString();
                proposal["inlineConflict"] = true;
            }
            state["proposal"] = proposal;
        }
        if (resolution.isEmpty()) addMessage(state, state["agentName"].toString(), reply["message"].toString(), "agent", {}, {}, conflictId);
    }
    if (automatic) state["activeRequest"] = m_activeRequest;
    if (persist(id, state) && automatic) applyProposal(id, state);
    publish(id);
    QTimer::singleShot(0, this, &Session::nextRequest);
}

void Session::agentError(const QString &message, const QString &code) {
    const auto id = m_agentProject;
    m_agentProject.clear();
    m_agentAuthor.clear();
    if (id.isEmpty()) { emit error(message); return; }
    auto state = m_workspace.load(id);
    if (m_activeRequest.contains("resolution") && state["proposal"].toObject()["id"] == m_activeRequest["resolution"]) {
        recordConflictOutcome(state, state["proposal"].toObject(), "The agreed request stopped before the app could be changed.");
        state["proposal"] = QJsonObject();
    }
    auto details=m_agent.diagnostics();
    if (!code.isEmpty()) { details["code"]=code; details["layer"]="centaur.coordinator"; }
    details["requestId"]=m_activities.value(id)["requestId"];
    const auto started=QDateTime::fromString(m_activities.value(id)["startedAt"].toString(),Qt::ISODateWithMs);
    if (started.isValid()) details["requestElapsedMs"]=qMax<qint64>(0,started.msecsTo(QDateTime::currentDateTimeUtc()));
    const auto before=m_activitySources.value(id); const auto after=appDigest(id);
    const bool verified=!before.isEmpty() && !after.isEmpty();
    details["sourceComparisonAvailable"]=verified;
    if (verified) details["sourceUnchanged"]=before==after;
    state.remove("activeRequest");
    auto imported=state.value("import").toObject();
    if (!imported.isEmpty() && !imported["previewReady"].toBool()) { imported["status"]="awaitingAnswer"; state["import"]=imported; }
    addMessage(state, state["agentName"].toString(), message+(verified && before==after ? " Your saved app is unchanged." : ""), "system");
    auto messages=state["messages"].toArray(); auto last=messages.last().toObject(); last["agentDiagnostics"]=details;
    messages[messages.size()-1]=last; state["messages"]=messages;
    endActivity(id);
    persist(id, state);
    publish(id);
    QTimer::singleShot(0, this, &Session::nextRequest);
}

void Session::applyProposal(const QString &id, QJsonObject state) {
    const auto path = m_workspace.projectPath(id);
    const bool gtk = state["appFormat"] == "gtk4-v1";
    const auto candidate = path + (gtk ? "/.centaur/candidate.gtk.json" : "/.centaur/candidate.qml");
    QString error;
    if (!Workspace::writeFile(candidate, proposalSource(state["proposal"].toObject()).toUtf8(), &error)) {
        emit this->error(error); return;
    }
    m_validatingProject = id;
    m_validatingEpoch = state["epoch"].toInt();
    auto env = QProcessEnvironment::systemEnvironment();
    if (!gtk) { env.insert("QT_QPA_PLATFORM", "offscreen"); env.insert("QT_QUICK_BACKEND", "software"); }
    m_validator.setProcessEnvironment(env);
    m_validator.start(runner(gtk), {"--check", candidate});
    advanceActivity(id,"validating");
    const int epoch = m_validatingEpoch;
    QTimer::singleShot(10000, &m_validator, [this, id, epoch] {
        if (m_validatingProject == id && m_validatingEpoch == epoch && m_validator.state() != QProcess::NotRunning) m_validator.kill();
    });
}

void Session::retryRequest(QJsonObject &state) {
    if (m_activeRequest.isEmpty() || m_activeRequest.contains("resolution")) return;
    auto queue = state["agentQueue"].toArray(); queue.prepend(m_activeRequest); state["agentQueue"] = queue;
}

QByteArray Session::appDigest(const QString &id) const {
    const auto state=m_workspace.load(id);
    if (state.isEmpty()) return {};
    QFile file(m_workspace.projectPath(id)+"/"+Workspace::sourceName(state));
    if (!file.exists()) return QByteArray("absent");
    if (!file.open(QIODevice::ReadOnly)) return {};
    const auto bytes=file.readAll();
    if (file.error()!=QFile::NoError) return {};
    return QCryptographicHash::hash(bytes,QCryptographicHash::Sha256);
}

void Session::beginActivity(const QString &id,const QJsonObject &request) {
    auto activity=m_activities.value(id);
    if (activity.isEmpty() || (request["continuationOf"]!=activity["requestId"] && request["id"]!=activity["requestId"])) {
        const auto messages=m_workspace.load(id)["messages"].toArray();
        activity=QJsonObject{{"requestId",request["id"]},{"startedAt",Workspace::now()},
            {"afterMessage",messages.isEmpty() ? QJsonValue("") : messages.last().toObject()["id"]}};
        m_activitySources[id]=appDigest(id);
    }
    m_expectedAgentRun=uid(); activity["runId"]=m_expectedAgentRun;
    activity["phase"]="starting"; activity["updatedAt"]=Workspace::now(); activity.remove("diagnostics");
    m_activities[id]=activity;
}

void Session::advanceActivity(const QString &id,const QString &phase,const QJsonObject &details) {
    if (!m_activities.contains(id)) return;
    auto activity=m_activities.value(id);
    activity["phase"]=phase; activity["updatedAt"]=Workspace::now();
    if (!details.isEmpty()) activity["diagnostics"]=details;
    m_activities[id]=activity;
    publish(id);
}

void Session::endActivity(const QString &id) {
    m_activities.remove(id); m_activitySources.remove(id);
}

void Session::settleActivity(const QString &id) {
    if (!m_activities.contains(id) || m_imports.contains(id) || m_validatingProject==id || (m_agentProject==id && m_agent.busy())) return;
    const QJsonValue requestId=m_activities.value(id).value("requestId");
    for (const auto &value:m_workspace.load(id)["agentQueue"].toArray())
        if (value.toObject()["continuationOf"]==requestId) return;
    endActivity(id); publish(id);
}

// 4df7f20 saved inferred references in the queue without identifying the
// requesting message. Rebind only against history present at that turn.
static void recoverQueuedReferences(QJsonObject &request, const QJsonObject &state) {
    if (request.contains("messageId") || request["attachments"].toArray().isEmpty()) return;
    const auto history = state["messages"].toArray();
    const auto origin = request["referenceMessage"].toString();
    qsizetype match = -1;
    bool foundOrigin = false;
    for (qsizetype i = 0; i < history.size(); ++i) {
        const auto row = history.at(i).toObject();
        if (row["id"] == origin) foundOrigin = true;
        if (!foundOrigin || row["kind"] != "human" || row["author"] != request["author"] ||
            row["text"] != request["text"] || row["participant"] != request["participant"]) continue;
        if (match >= 0) { match = -1; break; }
        match = i;
    }
    if (match < 0) {
        // A trimmed or ambiguous history cannot establish which file the user
        // requested. Never fetch an unrelated file on a resumed request.
        request["attachments"] = QJsonArray();
        request["referenceNote"] = "The originating message for this queued request could not be identified. If the task requires an attachment, ask the collaborator to attach it again.";
        request.remove("referenceMessage");
        request.remove("referenceAuthor");
        return;
    }
    const auto context = Attachments::agentContext(history, match, state["agentName"].toString("centaur"));
    for (auto it = context.begin(); it != context.end(); ++it) request[it.key()] = it.value();
    request["messageId"] = history.at(match).toObject()["id"];
}

void Session::nextRequest() {
    if (!m_host || m_updateStopping || !m_updateToken.isEmpty() || m_agent.busy() || !m_validatingProject.isEmpty() || m_validator.state() != QProcess::NotRunning) return;
    for (const auto &project : m_workspace.projects()) {
        const auto id = project.toMap()["id"].toString();
        auto state = m_workspace.load(id); auto queue = state["agentQueue"].toArray();
        if (m_imports.contains(id)) continue;
        const auto proposal = state["proposal"].toObject();
        if (isConflict(state)) {
            if (!proposal["resolving"].toBool()) continue;
            if (proposal["selected"] == "compromise") {
                m_activeRequest = {};
                applyProposal(id, state);
                publish(id);
                return;
            }
            m_activeRequest = proposal["choices"].toObject().value(proposal["selected"].toString()).toObject();
            m_activeRequest["resolution"] = proposal["id"];
        } else {
            if (queue.isEmpty()) continue;
            m_activeRequest = queue.first().toObject(); queue.removeFirst(); state["agentQueue"] = queue;
        }
        recoverQueuedReferences(m_activeRequest, state);
        state["activeRequest"] = m_activeRequest;
        if (!persist(id, state)) return;
        m_agentProject = id; m_agentAuthor = m_activeRequest["author"].toString(); m_agentEpoch = state["epoch"].toInt();
        beginActivity(id,m_activeRequest);
        auto request = state; request.remove("networkAcks"); request.remove("agentQueue"); request.remove("activeRequest");
        request.remove("directions");
        if (m_activeRequest.contains("resolution")) {
            request["approvedResolution"] = m_activeRequest["text"];
            request.remove("proposal");
        }
        request["logicalRequestId"]=m_activities.value(id).value("requestId");
        request.remove("importLocal");
        if (!state.value("import").toObject().isEmpty()) request["sourceInspection"] = state.value("importLocal").toObject()["context"];
        if (!state.value("import").toObject().isEmpty()) request["adaptationInspection"] = state.value("importLocal").toObject()["adaptation"];
        if (!state.value("import").toObject().isEmpty()) {
            const auto local=state["importLocal"].toObject(); auto diagnostics=local["diagnostics"].toObject();
            const auto failure=diagnostics["failure"].toObject();
            diagnostics["sourceAvailable"]=local["sourceAvailable"].toBool();
            diagnostics["capabilities"]=QJsonObject{{"terminal",false},{"inspection",true},
                {"isolatedDiagnostics",!qEnvironmentVariable("CENTAUR_IMPORT_SANDBOX").isEmpty() && !local["isolationUnavailable"].toBool()},
                {"retryAcquire",state["import"].toObject()["sourceType"]=="github" && !local["sourceAvailable"].toBool() && failure["retryable"].toBool()
                    && local["networkRemaining"].toInt()>0 && local["automaticRetries"].toInt()<1
                    && !state["import"].toObject()["previewReady"].toBool()}};
            request["importDiagnostics"]=diagnostics;
        }
        request["requestAuthor"] = m_agentAuthor; request["requestText"] = m_activeRequest["text"];
        request["requestComment"] = m_activeRequest["comment"];
        request["visualReferences"] = m_activeRequest["attachments"];
        request["referenceMessage"] = m_activeRequest["referenceMessage"];
        request["referenceAuthor"] = m_activeRequest["referenceAuthor"];
        if (m_activeRequest.contains("referenceNote")) request["referenceNote"] = m_activeRequest["referenceNote"];
        request["appHistory"] = !state.value("import").toObject().isEmpty() && !state.value("import").toObject()["previewReady"].toBool() ? QJsonArray() : m_workspace.history(id);
        const auto image = m_activeRequest["imageRevision"] == state["revision"] ? m_activeRequest["image"].toString() : QString();
        const bool pendingImport=!state.value("import").toObject().isEmpty() && !state.value("import").toObject()["previewReady"].toBool();
        // Select through OMP's supported --model option. Centaur's choice is
        // persisted in its own preferences; OMP credentials/config stay owned
        // by OMP. Read per request so an already-running host sees UI changes.
        const QSettings preferences(m_workspace.root() + "/preferences.ini", QSettings::IniFormat);
        m_agent.setModel(preferences.value("agent/model").toString());
        m_agent.ask(m_workspace.projectPath(id), request, pendingImport ? QString() : m_workspace.source(id), image,m_expectedAgentRun);
        publish(id); return;
    }
}
