#include "controller.h"
#include "collaboration.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QJsonDocument>
#include <QFile>
#include <QDir>
#include <QStandardPaths>
#include <QScopeGuard>
#include <QSslSocket>
#include <QTcpServer>
#include <memory>

static QJsonObject objectFile(const QString &path) {
    QFile file(path); if (!file.open(QIODevice::ReadOnly)) return {};
    return QJsonDocument::fromJson(file.readAll()).object();
}
static bool fakeAgent(const QString &path, const QJsonObject &reply) {
    const auto script = "#!" + QStandardPaths::findExecutable("sh").toUtf8() + "\ncat >/dev/null\nsleep 0.2\ncat <<'CENTAUR_REPLY'\n"
        + QJsonDocument(reply).toJson(QJsonDocument::Compact) + "\nCENTAUR_REPLY\n";
    return Workspace::writeFile(path, script) && QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
}
struct AgentEnv {
    QByteArray previous = qgetenv("CENTAUR_AGENT");
    bool existed = qEnvironmentVariableIsSet("CENTAUR_AGENT");
    explicit AgentEnv(const QString &path) { qputenv("CENTAUR_AGENT", path.toUtf8()); }
    ~AgentEnv() { if (existed) qputenv("CENTAUR_AGENT", previous); else qunsetenv("CENTAUR_AGENT"); }
};
struct Probe {
    QSslSocket socket;
    QByteArray buffer;
    QList<QJsonObject> messages;
    Probe(const QJsonObject &connection) {
        socket.setPeerVerifyMode(QSslSocket::VerifyNone);
        QObject::connect(&socket, &QSslSocket::encrypted, &socket, [this, connection] {
            send({{"type", "hello"}, {"version", 1}, {"project", connection["project"]}, {"memberToken", connection["memberToken"]}});
        });
        QObject::connect(&socket, &QSslSocket::readyRead, &socket, [this] {
            buffer += socket.readAll();
            while (buffer.contains('\n')) { const auto n = buffer.indexOf('\n'); messages.append(QJsonDocument::fromJson(buffer.left(n)).object()); buffer.remove(0, n + 1); }
        });
        socket.connectToHostEncrypted(connection["host"].toString(), quint16(connection["port"].toInt()));
    }
    ~Probe() { QObject::disconnect(&socket, nullptr, &socket, nullptr); socket.abort(); }
    void send(const QJsonObject &data) { socket.write(QJsonDocument(data).toJson(QJsonDocument::Compact) + '\n'); }
    bool has(const QString &type) const { for (const auto &m : messages) if (m["type"] == type) return true; return false; }
};
class NetworkTests : public QObject {
    Q_OBJECT
private slots:
    void initTestCase() {
        Q_INIT_RESOURCE(starter);
        QVERIFY(QSslSocket::supportsSsl());
        QTcpServer port; QVERIFY(port.listen(QHostAddress::LocalHost, 0));
        qputenv("CENTAUR_PORT", QByteArray::number(port.serverPort()));
    }
    void differentDataDirectoriesShareOnlyInvitedProjectAndAcceptedApp() {
        QTemporaryDir hostRoot, guestRoot;
        const auto fake = hostRoot.path() + "/agent";
        const QString source = "import QtQuick\nRectangle { width: 520; height: 640; color: \"green\" }\n";
        QVERIFY(fakeAgent(fake, {{"kind", "proposal"}, {"message", "Make it green"}, {"conflict", QJsonValue::Null}, {"qml", source}}));
        const AgentEnv env(fake);
        Controller host(hostRoot.path()); host.start(); host.setAuthor("Matt");
        host.createProject("PRIVATE OTHER PROJECT", "Must stay on host");
        const auto privateId = host.projectId();
        host.createProject("Family board", "Shared app"); const auto id = host.projectId();
        host.invitePeople("127.0.0.1"); QVERIFY(!host.invitationCode().isEmpty());
        Controller guest(guestRoot.path()); guest.start(); guest.joinProject(host.invitationCode(), "Saori");
        QTRY_COMPARE_WITH_TIMEOUT(guest.projectId(), id, 5000);
        QVERIFY(guest.remoteProject()); QVERIFY(guest.canContribute());
        QCOMPARE(host.connectionStatus(), QString("Host online"));
        QCOMPARE(guest.connectionStatus(), QString("Guest connected"));
        QCOMPARE(guest.projects().size(), 1); QCOMPARE(guest.author(), QString("Saori"));
        guest.sendMessage("Hello from another machine");
        QTRY_COMPARE(host.project().value("messages").toList().size(), 1);
        QCOMPARE(host.project().value("messages").toList().last().toMap()["author"].toString(), QString("Saori"));
        guest.addAnnotation({{"tool", "draw"}, {"points", QVariantList{QVariantMap{{"x", .2}, {"y", .3}}}}});
        QTRY_COMPARE(host.project().value("annotations").toList().size(), 1);
        guest.sendMessage("@centaur make it green");
        host.sendMessage("How was your day?"); // Ordinary chat must not starve an in-flight request.
        QTRY_COMPARE_WITH_TIMEOUT(host.project().value("revision").toInt(), 2, 15000);
        QTRY_COMPARE(guest.project().value("revision").toInt(), 2);
        QFile app(guestRoot.path() + "/shared/" + id + "/App.qml"); QVERIFY(app.open(QIODevice::ReadOnly)); QCOMPARE(QString::fromUtf8(app.readAll()), source);
        QFile snapshot(guestRoot.path() + "/shared/" + id + "/snapshot.json"); QVERIFY(snapshot.open(QIODevice::ReadOnly)); const auto bytes = snapshot.readAll();
        QVERIFY(!bytes.contains(privateId.toUtf8())); QVERIFY(!bytes.contains("PRIVATE OTHER PROJECT"));
        QVERIFY(!bytes.contains("networkAcks")); QVERIFY(!bytes.contains("memberToken")); QVERIFY(!bytes.contains(hostRoot.path().toUtf8()));
        QVERIFY(!QFileInfo::exists(guestRoot.path() + "/projects/" + id));
        const auto credential = guestRoot.path() + "/shared/" + id + "/connection.json";
        QVERIFY(!(QFileInfo(credential).permissions() & QFile::ReadOther));
        host.stopSharing();
        QTRY_VERIFY(guest.projectId().isEmpty());
        QTRY_VERIFY(!QFileInfo::exists(credential));
        QVERIFY(QFileInfo::exists(hostRoot.path() + "/projects/" + id + "/App.qml"));
    }
    void credentialsCannotImpersonateVoteManageOtherProjectsOrReplayCommands() {
        QTemporaryDir hostRoot, guestRoot;
        const auto fake = hostRoot.path() + "/agent";
        QVERIFY(fakeAgent(fake, {{"kind", "proposal"}, {"message", "Try a compromise"},
            {"conflict", QJsonObject{{"reason", "Blue and green conflict"}, {"authors", QJsonArray{"Matt", "Saori"}}}},
            {"qml", "import QtQuick\nRectangle { color: \"cyan\" }"}}));
        const AgentEnv env(fake);
        Controller host(hostRoot.path()); host.start(); host.setAuthor("Matt");
        host.createProject("Private", ""); const auto privateId = host.projectId();
        host.createProject("Shared", ""); const auto id = host.projectId();
        host.invitePeople("127.0.0.1"); const auto invitation = host.invitationCode();
        Controller guest(guestRoot.path()); guest.start(); guest.joinProject(invitation, "Saori");
        QTRY_COMPARE(guest.projectId(), id);
        guest.sendMessage("Green please"); host.sendMessage("Blue please");
        guest.sendMessage("@centaur reconcile our choices");
        QTRY_VERIFY_WITH_TIMEOUT(!host.project().value("proposal").toMap().isEmpty(), 10000);
        const auto connection = objectFile(guestRoot.path() + "/shared/" + id + "/connection.json");
        Probe probe(connection); QTRY_VERIFY(probe.has("welcome"));
        const auto next = connection["sequence"].toInt() + 1;
        probe.send({{"type", "accept"}, {"sequence", next}, {"projectId", id}, {"author", "Matt"}, {"baseRevision", 1}, {"proposalId", host.project().value("proposal").toMap()["id"].toString()}});
        QTRY_VERIFY(probe.has("ack"));
        QTRY_COMPARE(host.project().value("proposal").toMap()["accepted"].toList(), QVariantList{"Saori"});
        QCOMPARE(host.project().value("revision").toInt(), 1); // Cannot cast Matt's vote.
        host.acceptProposal(); QTRY_COMPARE_WITH_TIMEOUT(host.project().value("revision").toInt(), 2, 15000);
        probe.send({{"type", "message"}, {"sequence", next + 1}, {"projectId", id}, {"author", "Matt"}, {"text", "Exactly once"}});
        Workspace workspace(hostRoot.path());
        QTRY_COMPARE(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString(), QString("Exactly once"));
        QCOMPARE(workspace.load(id)["messages"].toArray().last().toObject()["author"].toString(), QString("Saori"));
        const auto count = workspace.load(id)["messages"].toArray().size();
        probe.send({{"type", "message"}, {"sequence", next + 1}, {"projectId", id}, {"text", "Duplicate"}});
        probe.send({{"type", "delete"}, {"sequence", next + 2}, {"projectId", privateId}});
        QTRY_VERIFY(probe.has("error"));
        QCOMPARE(workspace.load(id)["messages"].toArray().size(), count);
        QVERIFY(!workspace.load(privateId).isEmpty());
        QTemporaryDir intruderRoot;
        QString error;
        auto used = SharedProject::parseInvitation(invitation, &error); used["name"] = "Intruder";
        SharedProject intruder(intruderRoot.path(), used); QVERIFY(intruder.save()); intruder.start();
        QTRY_VERIFY(intruder.failed()); QVERIFY(intruder.state().isEmpty());
        host.stopSharing();
    }
    void pinnedHostIdentityAndReconnectPreserveTheSameMembership() {
        QTemporaryDir hostRoot, guestRoot, wrongRoot;
        auto host = std::make_unique<Controller>(hostRoot.path()); host->start(); host->setAuthor("Matt"); host->createProject("Shared", "");
        const auto id = host->projectId(); host->invitePeople("127.0.0.1");
        QString error;
        auto wrong = SharedProject::parseInvitation(host->invitationCode(), &error); wrong["pin"] = QString(64, '0'); wrong["name"] = "Wrong";
        SharedProject pinned(wrongRoot.path(), wrong); QVERIFY(pinned.save()); pinned.start(); QTRY_VERIFY(pinned.failed()); QVERIFY(pinned.state().isEmpty());
        auto connection = SharedProject::parseInvitation(host->invitationCode(), &error); connection["name"] = "Saori";
        SharedProject guest(guestRoot.path(), connection); QVERIFY(guest.save()); guest.start(); QTRY_VERIFY(guest.connected());
        const auto membership = objectFile(guest.path() + "/connection.json")["memberToken"].toString();
        host.reset(); QTRY_VERIFY(!guest.connected());
        host = std::make_unique<Controller>(hostRoot.path()); host->start();
        QTRY_VERIFY_WITH_TIMEOUT(guest.connected(), 10000);
        QCOMPARE(objectFile(guest.path() + "/connection.json")["memberToken"].toString(), membership);
        guest.send({{"type", "message"}, {"text", "After reconnect"}});
        Workspace workspace(hostRoot.path()); QTRY_COMPARE(workspace.load(id)["messages"].toArray().size(), 1);
        QCOMPARE(workspace.load(id)["messages"].toArray().first().toObject()["author"].toString(), QString("Saori"));
    }
    void lostAcknowledgementReplaysWithoutDuplicatingTheMessage() {
        QTemporaryDir hostRoot, guestRoot;
        Controller host(hostRoot.path()); host.start(); host.setAuthor("Matt"); host.createProject("Replay", "");
        const auto id = host.projectId(); host.invitePeople("127.0.0.1");
        QString error; auto connection = SharedProject::parseInvitation(host.invitationCode(), &error); connection["name"] = "Saori";
        auto guest = std::make_unique<SharedProject>(guestRoot.path(), connection); QVERIFY(guest->save()); guest->start(); QTRY_VERIFY(guest->connected());
        QVERIFY(guest->send({{"type", "message"}, {"text", "One message"}}));
        const auto file = guest->path() + "/connection.json";
        const auto unacknowledged = objectFile(file);
        QCOMPARE(unacknowledged["outbox"].toArray().size(), 1);
        Workspace workspace(hostRoot.path()); QTRY_COMPARE(workspace.load(id)["messages"].toArray().size(), 1);
        guest.reset();
        // Model a process stopping after the host committed, before the client
        // durably removed its acknowledged action from the outgoing queue.
        QVERIFY(Workspace::writeFile(file, QJsonDocument(unacknowledged).toJson()));
        guest = std::make_unique<SharedProject>(guestRoot.path(), objectFile(file)); guest->start();
        QTRY_VERIFY(guest->connected()); QTRY_VERIFY(objectFile(file)["outbox"].toArray().isEmpty());
        QCOMPARE(workspace.load(id)["messages"].toArray().size(), 1);
    }
    void twoGuestWindowsDoNotRaceTheDevicesOutgoingQueue() {
        QTemporaryDir hostRoot, guestRoot;
        Controller host(hostRoot.path()); host.start(); host.setAuthor("Matt"); host.createProject("Two windows", "");
        host.invitePeople("127.0.0.1");
        QString error; auto connection = SharedProject::parseInvitation(host.invitationCode(), &error); connection["name"] = "Saori";
        auto first = std::make_unique<SharedProject>(guestRoot.path(), connection); QVERIFY(first->save()); first->start(); QTRY_VERIFY(first->connected());
        const auto file = first->path() + "/connection.json";
        SharedProject second(guestRoot.path(), objectFile(file)); second.start(); QTRY_VERIFY(second.connected());
        QVERIFY(first->writable()); QVERIFY(!second.writable());
        QVERIFY(!second.send({{"type", "message"}, {"text", "Must retain draft"}}));
        QVERIFY(first->send({{"type", "message"}, {"text", "First window"}}));
        QTRY_VERIFY(objectFile(file)["outbox"].toArray().isEmpty());
        first.reset(); QTRY_VERIFY_WITH_TIMEOUT(second.writable(), 7000);
        QVERIFY(second.send({{"type", "message"}, {"text", "Second window"}}));
        Workspace workspace(hostRoot.path()); QTRY_COMPARE(workspace.load(host.projectId())["messages"].toArray().size(), 2);
    }
    void backgroundHostSurvivesItsOpeningWindow() {
        QTemporaryDir hostRoot, guestRoot;
        const auto fake = hostRoot.path() + "/agent";
        QVERIFY(fakeAgent(fake, {{"kind", "proposal"}, {"message", "Update while the window is closed"}, {"conflict", QJsonValue::Null}, {"qml", "import QtQuick\nRectangle { color: \"green\" }"}}));
        const AgentEnv env(fake);
        const auto stop = qScopeGuard([&] {
            QProcess::execute(QCoreApplication::applicationDirPath() + "/centaur-host", {"--stop", "--data-dir", hostRoot.path()});
        });
        QString id;
        auto owner = std::make_unique<Controller>(hostRoot.path()); owner->start(true); owner->setAuthor("Matt"); owner->createProject("Persistent host", "");
        QTRY_VERIFY_WITH_TIMEOUT(!owner->projectId().isEmpty(), 5000); id = owner->projectId();
        owner->invitePeople("127.0.0.1"); QTRY_VERIFY(!owner->invitationCode().isEmpty());
        QString error; auto connection = SharedProject::parseInvitation(owner->invitationCode(), &error); connection["name"] = "Saori";
        SharedProject guest(guestRoot.path(), connection); QVERIFY(guest.save()); guest.start(); QTRY_VERIFY(guest.connected());
        owner.reset();
        guest.send({{"type", "message"}, {"text", "The host window is closed"}});
        Workspace workspace(hostRoot.path()); QTRY_COMPARE(workspace.load(id)["messages"].toArray().size(), 1);
        QVERIFY(guest.connected());
        guest.send({{"type", "message"}, {"text", "@centaur make it green"}});
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["revision"].toInt(), 2, 15000);
        QTRY_COMPARE(guest.state()["revision"].toInt(), 2);
        Controller reopened(hostRoot.path()); reopened.start(true); QTRY_COMPARE(reopened.projects().size(), 1); reopened.openProject(id);
        QCOMPARE(reopened.project().value("messages").toList().size(), 4);
        reopened.stopSharing(); QTRY_VERIFY(guest.removed());
    }
};
QTEST_GUILESS_MAIN(NetworkTests)
#include "tst_network.moc"
