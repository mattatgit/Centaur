#include "session.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QFileInfo>
#include <QFile>
#include <QDir>
#include <QUuid>

static QString uid() { return QUuid::createUuid().toString(QUuid::WithoutBraces); }
static QString runner() {
    return qEnvironmentVariable("CENTAUR_PREVIEW", QCoreApplication::applicationDirPath() + "/centaur-preview");
}

Session::Session(const QString &root, QObject *parent) : QObject(parent), m_workspace(root) {
    m_socketName = "centaur-" + QString::fromLatin1(QCryptographicHash::hash(
        QFileInfo(root).absoluteFilePath().toUtf8(), QCryptographicHash::Sha256).toHex().left(24));
    connect(&m_server, &QLocalServer::newConnection, this, &Session::acceptConnection);
    connect(&m_client, &QLocalSocket::readyRead, this, [this] { read(&m_client); });
    connect(&m_client, &QLocalSocket::connected, this, [this] { m_starting = false; });
    connect(&m_client, &QLocalSocket::disconnected, this, [this] {
        if (!m_starting) emit error("The hosting window closed. Reopen Centaur to resume the saved project.");
    });
    connect(&m_agent, &Agent::completed, this, &Session::finishAgent);
    connect(&m_agent, &Agent::failed, this, &Session::agentError);
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
        addMessage(state, state["agentName"].toString(), "Could not start the native app checker. Your app is unchanged.", "system");
        persist(m_validatingProject, state);
        m_validatingProject.clear();
        publish();
    });
    connect(&m_validator, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
        [this](int code, QProcess::ExitStatus status) {
            const auto id = m_validatingProject;
            m_validatingProject.clear();
            auto state = m_workspace.load(id);
            QString error;
            if (state["epoch"].toInt() != m_validatingEpoch) {
                addMessage(state, state["agentName"].toString(), "The conversation changed while I checked the app. Ask me to prepare an updated proposal.", "system");
                state["proposal"] = QJsonObject();
            } else if (code != 0 || status != QProcess::NormalExit) {
                // QML diagnostics are local source errors, not provider credentials.
                const auto detail = QString::fromUtf8(m_validator.readAllStandardError()).right(1500);
                addMessage(state, state["agentName"].toString(), "The proposed app did not pass its native QML check. Your current app is still running.\n" + detail, "system");
                state["proposal"] = QJsonObject();
            } else {
                const auto proposal = state["proposal"].toObject();
                const auto archivePath = m_workspace.projectPath(id) + "/.centaur/annotations-v"
                    + QString::number(state["revision"].toInt()) + ".json";
                if (!Workspace::writeFile(archivePath, QJsonDocument(state["annotations"].toArray()).toJson(), &error)) {
                    addMessage(state, state["agentName"].toString(), "Could not preserve the current sketch: " + error, "system");
                } else if (m_workspace.applySource(id, proposal["qml"].toString(), proposal["message"].toString(), &error)) {
                    state["revision"] = state["revision"].toInt() + 1;
                    auto decisions = state["decisions"].toArray();
                    decisions.append(QJsonObject{{"summary", proposal["message"]}, {"authors", proposal["accepted"]},
                        {"requestedBy", proposal["requestedBy"]}, {"conflict", proposal["conflict"]},
                        {"restoredFrom", proposal["checkpoint"]},
                        {"revision", state["revision"]}, {"time", Workspace::now()}});
                    state["decisions"] = decisions;
                    state["contributors"] = QJsonArray();
                    state["annotations"] = QJsonArray();
                    state["proposal"] = QJsonObject();
                    addMessage(state, state["agentName"].toString(), proposal["kind"] == "restore"
                        ? "Restored that version of the app." : "Updated the app.", "agent");
                    emit sourceChanged(id);
                } else {
                    addMessage(state, state["agentName"].toString(), "Could not save the change: " + error, "system");
                }
            }
            persist(id, state);
            publish(id);
        });
}

Session::~Session() {
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

void Session::start() {
    m_lock = std::make_unique<QLockFile>(m_workspace.root() + "/session.lock");
    // QLockFile detects a dead host; never unlink a live host's socket.
    if (m_lock->tryLock(0)) {
        QLocalServer::removeServer(m_socketName);
        m_server.setSocketOptions(QLocalServer::UserAccessOption);
        if (!m_server.listen(m_socketName)) { emit error(m_server.errorString()); return; }
        m_host = true;
        m_starting = false;
        for (const auto &project : m_workspace.projects()) {
            const auto id = project.toMap()["id"].toString();
            auto state = m_workspace.load(id);
            const auto proposal = state["proposal"].toObject();
            // Do not auto-apply proposals made under the old everyone-agrees
            // policy, or resume an interrupted automatic check without context.
            if (!proposal.isEmpty() && !proposal["conflict"].isObject()) {
                state["proposal"] = QJsonObject();
                addMessage(state, state["agentName"].toString(), "An unfinished change wasn't applied. Ask me again to continue.", "system");
                persist(id, state);
            }
        }
        publish();
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
        });
        publish();
    }
}

void Session::reply(QLocalSocket *socket, const QJsonObject &data) {
    if (socket) socket->write(QJsonDocument(data).toJson(QJsonDocument::Compact) + '\n');
    else if (data["type"] == "error") emit error(data["message"].toString());
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
    for (const auto &project : m_workspace.projects()) states.append(m_workspace.load(project.toMap()["id"].toString()));
    QJsonObject data{{"type", "snapshot"}, {"projects", QJsonArray::fromVariantList(m_workspace.projects())},
        {"states", states}, {"agentAvailable", m_agent.available()}, {"agentExecutable", m_agent.executable()},
        {"busyProject", m_agent.busy() ? m_agentProject : m_validatingProject}, {"changedProject", id}};
    emit snapshot(data);
    for (auto *peer : m_peers) reply(peer, data);
}

void Session::addMessage(QJsonObject &state, const QString &author, const QString &text, const QString &kind) {
    auto messages = state["messages"].toArray();
    const QJsonObject message{{"id", uid()}, {"author", author}, {"text", text}, {"kind", kind},
        {"time", Workspace::now()}, {"revision", state["revision"]}};
    messages.append(message);
    QFile history(m_workspace.projectPath(state["id"].toString()) + "/.centaur/conversation.jsonl");
    if (history.open(QIODevice::WriteOnly | QIODevice::Append))
        history.write(QJsonDocument(message).toJson(QJsonDocument::Compact) + '\n');
    // Bound live state and model context on modest hardware.
    while (messages.size() > 250) messages.removeFirst();
    state["messages"] = messages;
}

bool Session::persist(const QString &id, QJsonObject state) {
    state["updated"] = Workspace::now();
    QString error;
    if (m_workspace.save(id, state, &error)) return true;
    emit this->error("Could not save the project: " + error);
    return false;
}

void Session::handle(const QJsonObject &command, QLocalSocket *sender) {
    const auto type = command["type"].toString();
    auto fail = [this, sender](const QString &message) { reply(sender, {{"type", "error"}, {"message", message}}); };
    if (type == "create" || type == "openStarter") {
        // Only the host has the authoritative list at startup. Resolve this in
        // one command so joining windows cannot each create a starter project.
        const bool starter = type == "openStarter";
        const auto projects = starter ? m_workspace.projects() : QVariantList();
        QString error;
        const auto id = !projects.isEmpty() ? projects.first().toMap()["id"].toString()
            : m_workspace.createProject(starter ? "Family board" : command["name"].toString(),
                starter ? "A little space for everyday things, made together." : command["description"].toString(), &error);
        if (id.isEmpty()) { fail(error); return; }
        publish(id);
        reply(sender, {{"type", starter ? "opened" : "created"}, {"projectId", id}});
        return;
    }
    const auto id = command["projectId"].toString();
    auto state = m_workspace.load(id);
    if (state.isEmpty()) { fail("That project is unavailable."); return; }
    const auto author = command["author"].toString().trimmed().left(50);
    if (author.isEmpty()) { fail("Choose your name before contributing."); return; }
    if (type == "message") {
        const auto text = command["text"].toString().trimmed().left(12000);
        if (text.isEmpty()) return;
        addMessage(state, author, text);
        auto contributors = state["contributors"].toArray();
        if (!contributors.contains(author)) contributors.append(author);
        state["contributors"] = contributors;
        state["epoch"] = state["epoch"].toInt() + 1;
        state["proposal"] = QJsonObject();
        if (!persist(id, state)) return;
        const auto mention = "@" + state["agentName"].toString();
        if (text.contains(mention, Qt::CaseInsensitive)) {
            if (m_agent.busy() || !m_validatingProject.isEmpty()) {
                fail("The agent is busy. Your message is saved; address it again when it finishes.");
            } else {
                m_agentProject = id;
                m_agentAuthor = author;
                m_agentEpoch = state["epoch"].toInt();
                QString image;
                const auto filename = command["image"].toString();
                const auto expected = m_workspace.projectPath(id) + "/.centaur/";
                const auto canonical = QFileInfo(filename).canonicalFilePath();
                if (canonical.startsWith(expected) && canonical.endsWith(".png")
                    && command["imageRevision"] == state["revision"]) image = canonical;
                auto request = state;
                request["requestAuthor"] = author;
                request["appHistory"] = m_workspace.history(id);
                m_agent.ask(m_workspace.projectPath(id), request, m_workspace.source(id), image);
            }
        }
    } else if (type == "annotation") {
        auto annotation = command["annotation"].toObject();
        const auto points = annotation["points"].toArray();
        if (points.isEmpty() || points.size() > 4096) { fail("That drawing is too large."); return; }
        if (annotation["tool"] != "draw" && annotation["tool"] != "comment") return;
        for (const auto &value : points) {
            const auto point = value.toObject();
            if (!point["x"].isDouble() || !point["y"].isDouble()
                || point["x"].toDouble() < 0 || point["x"].toDouble() > 1
                || point["y"].toDouble() < 0 || point["y"].toDouble() > 1) return;
        }
        auto annotations = state["annotations"].toArray();
        int pointCount = points.size();
        for (const auto &mark : annotations) pointCount += mark.toObject()["points"].toArray().size();
        if (annotations.size() >= 100 || pointCount > 16384) { fail("This canvas is full. Undo some marks or build this change before adding more."); return; }
        annotation["id"] = uid(); annotation["author"] = author;
        annotation["revision"] = state["revision"]; annotation["time"] = Workspace::now();
        annotations.append(annotation);
        state["annotations"] = annotations;
        state["epoch"] = state["epoch"].toInt() + 1;
        state["proposal"] = QJsonObject();
        auto contributors = state["contributors"].toArray();
        if (!contributors.contains(author)) contributors.append(author);
        state["contributors"] = contributors;
        persist(id, state);
    } else if (type == "undo") {
        auto annotations = state["annotations"].toArray();
        for (int i = annotations.size() - 1; i >= 0; --i) {
            if (annotations[i].toObject()["author"] == author && annotations[i].toObject()["revision"] == state["revision"]) {
                annotations.removeAt(i); break;
            }
        }
        state["annotations"] = annotations;
        state["epoch"] = state["epoch"].toInt() + 1;
        state["proposal"] = QJsonObject();
        persist(id, state);
    } else if (type == "accept") {
        auto proposal = state["proposal"].toObject();
        if (proposal.isEmpty() || proposal["id"] != command["proposalId"]
            || proposal["epoch"] != state["epoch"]) { fail("That proposal has changed. Review the latest one."); return; }
        if (!proposal["conflict"].isObject()) { fail("Only conflicting requests need agreement. Ask the agent to prepare this change again."); return; }
        if (!m_validatingProject.isEmpty() || m_agent.busy()) { fail("The agent is already working."); return; }
        if (!proposal["authors"].toArray().contains(author)) { fail("This conflict needs agreement only from the people whose requests conflict."); return; }
        auto accepted = proposal["accepted"].toArray();
        if (!accepted.contains(author)) accepted.append(author);
        proposal["accepted"] = accepted;
        state["proposal"] = proposal;
        if (!persist(id, state)) return;
        bool everyone = true;
        for (const auto &contributor : proposal["authors"].toArray()) if (!accepted.contains(contributor)) everyone = false;
        if (everyone) applyProposal(id, state);
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
        if (m_agentProject == id && m_agent.busy()) { fail("Wait for the agent to finish before deleting."); return; }
        if (m_validatingProject == id) { fail("Wait for the app check to finish before deleting."); return; }
        QString error;
        if (!m_workspace.deleteProject(id, &error)) { fail(error); return; }
    } else if (type == "archive") {
        if (m_agentProject == id && m_agent.busy()) { fail("Wait for the agent to finish before archiving."); return; }
        if (m_validatingProject == id) { fail("Wait for the app check to finish before archiving."); return; }
        state["archived"] = true;
        persist(id, state);
    } else if (type == "cancel") {
        if (m_agentProject == id && m_agent.busy()) {
            m_agent.cancel();
            m_agentProject.clear();
            m_agentAuthor.clear();
            addMessage(state, state["agentName"].toString(), author + " stopped the agent. Your app is unchanged.", "system");
            persist(id, state);
        }
    }
    publish(id);
}

void Session::finishAgent(const QJsonObject &reply) {
    const auto id = m_agentProject;
    const auto requester = m_agentAuthor;
    m_agentProject.clear();
    m_agentAuthor.clear();
    auto state = m_workspace.load(id);
    bool automatic = false;
    if (state["epoch"].toInt() != m_agentEpoch) {
        addMessage(state, state["agentName"].toString(), "New messages or drawings arrived while I was thinking. Address me again so I can include them.", "system");
    } else {
        if (reply["kind"] == "proposal" || reply["kind"] == "restore") {
            auto proposal = reply;
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
                proposal["qml"] = source;
            } else proposal.remove("checkpoint");
            const auto conflict = reply["conflict"];
            QJsonArray authors{requester};
            if (conflict.isObject()) {
                authors = conflict.toObject()["authors"].toArray();
                QSet<QString> knownAuthors;
                for (const auto &value : state["messages"].toArray()) {
                    const auto message = value.toObject();
                    if (message["kind"] == "human") knownAuthors.insert(message["author"].toString());
                }
                for (const auto &value : state["annotations"].toArray())
                    knownAuthors.insert(value.toObject()["author"].toString());
                for (const auto &value : state["decisions"].toArray())
                    for (const auto &author : value.toObject()["authors"].toArray()) knownAuthors.insert(author.toString());
                for (const auto &author : authors) {
                    if (knownAuthors.contains(author.toString())) continue;
                    addMessage(state, state["agentName"].toString(), "I couldn't identify the people involved in that conflict. Please clarify whose requests differ and ask me again.", "system");
                    persist(id, state);
                    publish(id);
                    return;
                }
            }
            proposal["id"] = uid(); proposal["epoch"] = m_agentEpoch;
            proposal["requestedBy"] = requester;
            proposal["authors"] = authors;
            automatic = conflict.isNull();
            proposal["accepted"] = automatic ? QJsonArray{requester} : QJsonArray();
            state["proposal"] = proposal;
        }
        addMessage(state, state["agentName"].toString(), reply["message"].toString(), "agent");
    }
    if (persist(id, state) && automatic) applyProposal(id, state);
    publish(id);
}

void Session::agentError(const QString &message) {
    const auto id = m_agentProject;
    m_agentProject.clear();
    m_agentAuthor.clear();
    if (id.isEmpty()) { emit error(message); return; }
    auto state = m_workspace.load(id);
    addMessage(state, state["agentName"].toString(), message, "system");
    persist(id, state);
    publish(id);
}

void Session::applyProposal(const QString &id, QJsonObject state) {
    const auto path = m_workspace.projectPath(id);
    QString error;
    if (!Workspace::writeFile(path + "/.centaur/candidate.qml", state["proposal"].toObject()["qml"].toString().toUtf8(), &error)) {
        emit this->error(error); return;
    }
    m_validatingProject = id;
    m_validatingEpoch = state["epoch"].toInt();
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("QT_QPA_PLATFORM", "offscreen");
    env.insert("QT_QUICK_BACKEND", "software");
    m_validator.setProcessEnvironment(env);
    m_validator.start(runner(), {"--check", path + "/.centaur/candidate.qml"});
    const int epoch = m_validatingEpoch;
    QTimer::singleShot(10000, &m_validator, [this, id, epoch] {
        if (m_validatingProject == id && m_validatingEpoch == epoch && m_validator.state() != QProcess::NotRunning) m_validator.kill();
    });
}
