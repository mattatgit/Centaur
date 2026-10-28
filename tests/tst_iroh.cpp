#include "controller.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QFile>
#include <QJsonDocument>
#include <QStandardPaths>
#include <QTcpServer>
#include <QScopeGuard>

static QJsonObject objectFile(const QString &path) {
    QFile file(path); if (!file.open(QIODevice::ReadOnly)) return {};
    return QJsonDocument::fromJson(file.readAll()).object();
}
static QString encoded(QJsonObject data) {
    return "centaur2:" + QJsonDocument(data).toJson(QJsonDocument::Compact).toBase64(QByteArray::Base64UrlEncoding | QByteArray::OmitTrailingEquals);
}
class IrohTests : public QObject {
    Q_OBJECT
private slots:
    void initTestCase() {
        Q_INIT_RESOURCE(starter);
        QVERIFY(QFileInfo::exists(QCoreApplication::applicationDirPath() + "/centaur-network"));
        QTcpServer port; QVERIFY(port.listen(QHostAddress::LocalHost, 0)); qputenv("CENTAUR_PORT", QByteArray::number(port.serverPort()));
    }
    void concurrentGuestsAgentAndLegacyLanStayInTheSameProject() {
        QTemporaryDir home, first, second, legacy;
        const auto fake = home.path() + "/agent";
        const QString source = "import QtQuick\nRectangle { width: 520; height: 640; color: \"green\" }\n";
        const auto script = "#!" + QStandardPaths::findExecutable("sh").toUtf8() + "\ncat >/dev/null\ncat <<'REPLY'\n"
            + QJsonDocument(QJsonObject{{"kind", "proposal"}, {"message", "Make it green"}, {"conflict", QJsonValue::Null}, {"qml", source}}).toJson(QJsonDocument::Compact) + "\nREPLY\n";
        QVERIFY(Workspace::writeFile(fake, script)); QVERIFY(QFile::setPermissions(fake, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        const auto previous = qgetenv("CENTAUR_AGENT"); const bool hadAgent = qEnvironmentVariableIsSet("CENTAUR_AGENT");
        const auto restore = qScopeGuard([&] { if (hadAgent) qputenv("CENTAUR_AGENT", previous); else qunsetenv("CENTAUR_AGENT"); }); qputenv("CENTAUR_AGENT", fake.toUtf8());
        Controller host(home.path()); host.start(); host.setAuthor("Matt"); host.createProject("Private", "Private"); const auto privateId = host.projectId();
        host.createProject("Shared", ""); const auto id = host.projectId();
        host.invitePeople("iroh"); QTRY_VERIFY_WITH_TIMEOUT(!host.invitationCode().isEmpty(), 25000); QVERIFY(host.invitationCode().startsWith("centaur2:"));
        const auto used = host.invitationCode();
        Controller a(first.path()); a.start(); a.joinProject(used, "Saori"); QTRY_COMPARE_WITH_TIMEOUT(a.projectId(), id, 40000);
        host.invitePeople("iroh"); QTRY_VERIFY_WITH_TIMEOUT(!host.invitationCode().isEmpty(), 10000);
        Controller b(second.path()); b.start(); b.joinProject(host.invitationCode(), "Chris"); QTRY_COMPARE_WITH_TIMEOUT(b.projectId(), id, 40000);
        SharedProject extraWindow(first.path(), objectFile(first.path() + "/shared/" + id + "/connection.json"));
        extraWindow.start(); QTRY_VERIFY_WITH_TIMEOUT(extraWindow.connected(), 40000); QVERIFY(!extraWindow.writable());
        host.invitePeople("127.0.0.1"); QVERIFY(host.invitationCode().startsWith("centaur1:"));
        Controller lan(legacy.path()); lan.start(); lan.joinProject(host.invitationCode(), "Alex"); QTRY_COMPARE(lan.projectId(), id);
        QVERIFY(a.sendMessage("From Iroh A")); QVERIFY(b.sendMessage("From Iroh B")); QVERIFY(lan.sendMessage("From LAN"));
        QTRY_COMPARE(host.project().value("messages").toList().size(), 3);
        QTRY_COMPARE(a.project().value("messages").toList().size(), 3); QTRY_COMPARE(b.project().value("messages").toList().size(), 3);
        a.addAnnotation({{"tool", "draw"}, {"points", QVariantList{QVariantMap{{"x", .2}, {"y", .3}}}}});
        QTRY_COMPARE(b.project().value("annotations").toList().size(), 1);
        QVERIFY(b.sendMessage("@centaur make it green"));
        QTRY_COMPARE_WITH_TIMEOUT(host.project().value("revision").toInt(), 2, 15000);
        QTRY_COMPARE(a.project().value("revision").toInt(), 2); QTRY_COMPARE(b.project().value("revision").toInt(), 2);
        QFile app(first.path() + "/shared/" + id + "/App.qml"); QVERIFY(app.open(QIODevice::ReadOnly)); QCOMPARE(app.readAll(), source.toUtf8());
        QCOMPARE(a.projects().size(), 1); QVERIFY(!a.projects().first().toMap().values().contains(privateId));
        QTemporaryDir replayRoot; QString error; auto replayConnection = SharedProject::parseInvitation(used, &error); replayConnection["name"] = "Replay";
        SharedProject replay(replayRoot.path(), replayConnection); QVERIFY(replay.save()); replay.start(); QTRY_VERIFY_WITH_TIMEOUT(replay.failed(), 40000); QVERIFY(replay.state().isEmpty());
        host.stopSharing(); QTRY_VERIFY(a.projectId().isEmpty()); QTRY_VERIFY(b.projectId().isEmpty()); QTRY_VERIFY(lan.projectId().isEmpty()); QTRY_VERIFY(extraWindow.removed());
        QTRY_VERIFY(!QFileInfo::exists(first.path() + "/shared/" + id + "/connection.json"));
    }
    void pinnedIdentityRestartAndCachedMembership() {
        QTemporaryDir home, guestRoot, wrongRoot;
        auto host = std::make_unique<Controller>(home.path()); host->start(); host->setAuthor("Matt"); host->createProject("Shared", "");
        const auto id = host->projectId(); host->invitePeople("iroh"); QTRY_VERIFY_WITH_TIMEOUT(!host->invitationCode().isEmpty(), 25000);
        QString error; auto connection = SharedProject::parseInvitation(host->invitationCode(), &error); QVERIFY(!connection.isEmpty()); connection["name"] = "Saori";
        auto wrong = connection; wrong["memberToken"] = QString(43, 'a'); wrong["pin"] = QString(64, '0'); wrong["name"] = "Wrong";
        SharedProject pinned(wrongRoot.path(), wrong); QVERIFY(pinned.save()); pinned.start(); QTRY_VERIFY_WITH_TIMEOUT(pinned.failed(), 40000); QVERIFY(pinned.state().isEmpty());
        SharedProject guest(guestRoot.path(), connection); QVERIFY(guest.save()); guest.start(); QTRY_VERIFY_WITH_TIMEOUT(guest.connected(), 40000);
        const QJsonValue credential = objectFile(guest.path() + "/connection.json")["memberToken"];
        QFile key(home.path() + "/network/iroh.key"); QVERIFY(key.open(QIODevice::ReadOnly)); const auto identity = key.readAll(); QCOMPARE(identity.size(), 32);
        QVERIFY(!(QFileInfo(key).permissions() & (QFile::ReadGroup | QFile::ReadOther)));
        host.reset(); QTRY_VERIFY(!guest.connected()); QVERIFY(!guest.send({{"type", "message"}, {"text", "offline"}}));
        host = std::make_unique<Controller>(home.path()); host->start(); host->openProject(id);
        QTRY_VERIFY_WITH_TIMEOUT(guest.connected(), 45000);
        QCOMPARE(objectFile(guest.path() + "/connection.json")["memberToken"], credential);
        QVERIFY(guest.send({{"type", "message"}, {"text", "After restart"}})); QTRY_COMPARE(host->project().value("messages").toList().size(), 1);
        host->stopSharing(); QTRY_VERIFY(guest.removed());
    }
    void backgroundHostKeepsSharingAfterItsWindowCloses() {
        QTemporaryDir home, guestRoot;
        const auto stop = qScopeGuard([&] {
            QProcess::execute(QCoreApplication::applicationDirPath() + "/centaur-host", {"--stop", "--data-dir", home.path()});
        });
        auto owner = std::make_unique<Controller>(home.path()); owner->start(true); owner->setAuthor("Matt"); owner->createProject("Background Iroh", "");
        QTRY_VERIFY(!owner->projectId().isEmpty()); const auto id = owner->projectId();
        owner->invitePeople("iroh"); QTRY_VERIFY_WITH_TIMEOUT(!owner->invitationCode().isEmpty(), 25000);
        QString error; auto connection = SharedProject::parseInvitation(owner->invitationCode(), &error); connection["name"] = "Saori";
        SharedProject guest(guestRoot.path(), connection); QVERIFY(guest.save()); guest.start(); QTRY_VERIFY_WITH_TIMEOUT(guest.connected(), 40000);
        owner.reset(); QVERIFY(guest.send({{"type", "message"}, {"text", "Owner window is closed"}}));
        Workspace workspace(home.path()); QTRY_COMPARE(workspace.load(id)["messages"].toArray().size(), 1);
        Controller reopened(home.path()); reopened.start(true); QTRY_COMPARE(reopened.projects().size(), 1); reopened.openProject(id);
        reopened.stopSharing(); QTRY_VERIFY(guest.removed());
    }
    void legacyMembershipSurvivesAddingInternetSharingAndRestart() {
        QTemporaryDir home, guestRoot;
        auto host = std::make_unique<Controller>(home.path()); host->start(); host->setAuthor("Matt"); host->createProject("Legacy", "");
        const auto id = host->projectId(); host->invitePeople("127.0.0.1");
        QString error; auto connection = SharedProject::parseInvitation(host->invitationCode(), &error); connection["name"] = "Saori";
        SharedProject guest(guestRoot.path(), connection); QVERIFY(guest.save()); guest.start(); QTRY_VERIFY(guest.connected());
        host.reset();
        // Model a v0.2 shares file, before transport flags existed.
        const auto file = home.path() + "/network/shares.json";
        auto shares = objectFile(file); auto share = shares[id].toObject(); share.remove("lan"); share.remove("iroh"); shares[id] = share;
        QVERIFY(Workspace::writeFile(file, QJsonDocument(shares).toJson()));
        host = std::make_unique<Controller>(home.path()); host->start(); host->openProject(id); QTRY_VERIFY_WITH_TIMEOUT(guest.connected(), 10000);
        host->invitePeople("iroh"); QTRY_VERIFY_WITH_TIMEOUT(!host->invitationCode().isEmpty(), 25000);
        QVERIFY(objectFile(file)[id].toObject()["lan"].toBool());
        host.reset(); QTRY_VERIFY(!guest.connected());
        host = std::make_unique<Controller>(home.path()); host->start(); host->openProject(id); QTRY_VERIFY_WITH_TIMEOUT(guest.connected(), 15000);
        QVERIFY(guest.send({{"type", "message"}, {"text", "Original LAN membership"}})); QTRY_COMPARE(host->project().value("messages").toList().size(), 1);
        host->stopSharing(); QTRY_VERIFY(guest.removed());
    }
    void malformedInvitationsCannotSupplyArbitraryConfiguration() {
        QJsonObject data{{"version", 2}, {"transport", "iroh"}, {"project", QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"pin", QString(64, 'a')}, {"invite", QString(43, 'b')}, {"endpoint", QJsonObject{{"node", QString(64, 'c')}, {"addresses", QJsonArray{"127.0.0.1:1234"}}, {"relay", "https://relay.example.com"}}}};
        QString error; auto valid = SharedProject::parseInvitation(encoded(data), &error); QVERIFY(!valid.isEmpty());
        data["path"] = "/tmp/other-project"; data["helper"] = "/tmp/executable";
        valid = SharedProject::parseInvitation(encoded(data), &error); QVERIFY(!valid.contains("path")); QVERIFY(!valid.contains("helper"));
        auto endpoint = data["endpoint"].toObject(); endpoint["relay"] = "https://user:secret@relay.example.com"; data["endpoint"] = endpoint;
        QVERIFY(SharedProject::parseInvitation(encoded(data), &error).isEmpty());
        endpoint["relay"] = "https://relay.example.com"; endpoint["addresses"] = QJsonArray{"0.0.0.0:1234"}; data["endpoint"] = endpoint;
        QVERIFY(SharedProject::parseInvitation(encoded(data), &error).isEmpty());
    }
};
QTEST_GUILESS_MAIN(IrohTests)
#include "tst_iroh.moc"
