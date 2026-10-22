#include "workspace.h"
#include "session.h"
#include "agent.h"
#include "inkitem.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QStandardPaths>

class CoreTests : public QObject {
    Q_OBJECT
private slots:
    void initTestCase() { Q_INIT_RESOURCE(starter); }
    void projectsArePersistentGitRepos() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Family board", "Make it together", &error);
        QVERIFY2(!id.isEmpty(), qPrintable(error));
        QVERIFY(QFile::exists(workspace.projectPath(id) + "/.git/HEAD"));
        QVERIFY(workspace.source(id).contains("QtQuick"));
        QCOMPARE(workspace.projects().size(), 1);
        Workspace reopened(dir.path());
        QCOMPARE(reopened.load(id)["name"].toString(), QString("Family board"));
        QVERIFY(workspace.createProject("   ", "", &error).isEmpty());
        QVERIFY(workspace.projectPath("../../etc").isEmpty());
        QVERIFY(workspace.load("../../etc").isEmpty());
    }
    void checkpointsPreservePreviousSource() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        auto id = workspace.createProject("Test", "", &error);
        const auto old = workspace.source(id);
        const auto next = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'blue' }");
        QVERIFY2(workspace.applySource(id, next, "Try blue", &error), qPrintable(error));
        QCOMPARE(workspace.source(id), next);
        QFile previous(workspace.projectPath(id) + "/.centaur/previous.qml");
        QVERIFY(previous.open(QIODevice::ReadOnly));
        QCOMPARE(QString::fromUtf8(previous.readAll()), old);
    }
    void agentResponsesAreValidated() {
        QString error;
        QVERIFY(Agent::parseReply("not json", &error).isEmpty());
        QVERIFY(Agent::parseReply(R"({"kind":"proposal","message":"Done"})", &error).isEmpty());
        QVERIFY(Agent::parseReply(R"({"kind":"anything","message":"Done"})", &error).isEmpty());
        QCOMPARE(Agent::parseReply("```json\n{\"kind\":\"question\",\"message\":\"Which is better?\"}\n```", &error)["kind"].toString(), QString("question"));
    }
    void interactionModeDoesNotInterceptAppClicks() {
        InkItem layer;
        QCOMPARE(layer.acceptedMouseButtons(), Qt::NoButton);
        layer.setTool("draw");
        QCOMPARE(layer.acceptedMouseButtons(), Qt::LeftButton);
        layer.setTool("interact");
        QCOMPARE(layer.acceptedMouseButtons(), Qt::NoButton);
    }
    void drawingAfterACommentHasNoFill_data() {
        QTest::addColumn<bool>("closed");
        QTest::newRow("open stroke") << false;
        QTest::newRow("closed stroke") << true;
    }
    void drawingAfterACommentHasNoFill() {
        QFETCH(bool, closed);
        InkItem layer;
        layer.setSize(QSizeF(256, 256));
        const auto point = [](double x, double y) {
            return QVariantMap{{"x", x}, {"y", y}};
        };
        QVariantList drawing{point(0.25, 0.25), point(0.75, 0.25), point(0.75, 0.75)};
        if (closed) drawing.append(point(0.25, 0.25));
        layer.setAnnotations({
            QVariantMap{{"tool", "comment"}, {"points", QVariantList{point(0.05, 0.05), point(0.15, 0.15)}}},
            QVariantMap{{"tool", "draw"}, {"points", drawing}}
        });
        QImage image(256, 256, QImage::Format_ARGB32_Premultiplied);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        layer.paint(&painter);
        painter.end();
        // Both open and closed outlines must leave the underlying app visible.
        QCOMPARE(image.pixelColor(160, 96).alpha(), 0);
        QCOMPARE(image.pixelColor(128, 64), QColor("#426bc9"));
        QVERIFY(image.pixelColor(13, 13).alpha() > 0); // Comment anchor still renders.
    }
    void anAgentProposalIncludesBothAuthors() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/fake-agent";
        const auto reply = QJsonDocument(QJsonObject{{"kind", "proposal"},
            {"message", "Keep navigation short, with every section reachable."},
            {"qml", "import QtQuick\nRectangle { width: 520; height: 640; color: 'green' }"}}).toJson(QJsonDocument::Compact);
        const auto shell = QStandardPaths::findExecutable("sh").toUtf8();
        QVERIFY(!shell.isEmpty());
        QVERIFY(Workspace::writeFile(fake, "#!" + shell + "\ncat <<'CENTAUR_REPLY'\n" + reply + "\nCENTAUR_REPLY\n"));
        QVERIFY(QFile::setPermissions(fake, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        const auto previousAgent = qgetenv("CENTAUR_AGENT");
        qputenv("CENTAUR_AGENT", fake.toUtf8());
        Session session(dir.path()); session.start();
        session.send({{"type", "create"}, {"name", "Negotiate"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        const auto initial = workspace.source(id);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "Keep navigation simple"}});
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "@centaur keep every section easy to reach"}});
        QTRY_VERIFY_WITH_TIMEOUT(!workspace.load(id)["proposal"].toObject().isEmpty(), 5000);
        const auto proposal = workspace.load(id)["proposal"].toObject();
        QCOMPARE(proposal["authors"].toArray(), (QJsonArray{"Matt", "Saori"}));
        QCOMPARE(workspace.source(id), initial);
        qputenv("CENTAUR_AGENT", previousAgent);
    }
    void newDiscussionInvalidatesAnInFlightAgentReply() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/slow-agent";
        const auto reply = QJsonDocument(QJsonObject{{"kind", "proposal"}, {"message", "Try blue"},
            {"qml", "import QtQuick\nRectangle { color: 'blue' }"}}).toJson(QJsonDocument::Compact);
        const auto shell = QStandardPaths::findExecutable("sh").toUtf8();
        QVERIFY(!shell.isEmpty());
        QVERIFY(Workspace::writeFile(fake, "#!" + shell + "\nsleep 0.2\ncat <<'CENTAUR_REPLY'\n" + reply + "\nCENTAUR_REPLY\n"));
        QVERIFY(QFile::setPermissions(fake, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        const auto previousAgent = qgetenv("CENTAUR_AGENT");
        qputenv("CENTAUR_AGENT", fake.toUtf8());
        Session session(dir.path()); session.start();
        session.send({{"type", "create"}, {"name", "Changing direction"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "@centaur make it blue"}});
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "Wait, can we discuss the colour?"}});
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["messages"].toArray().size(), 3, 5000);
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
        QVERIFY(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString().contains("New messages"));
        QCOMPARE(workspace.load(id)["revision"].toInt(), 1);
        qputenv("CENTAUR_AGENT", previousAgent);
    }
    void twoWindowsShareAuthoredMessages() {
        QTemporaryDir dir;
        Session host(dir.path());
        QSignalSpy hostSpy(&host, &Session::snapshot);
        host.start();
        QVERIFY(host.isHost());
        Session guest(dir.path());
        QSignalSpy guestSpy(&guest, &Session::snapshot);
        guest.start();
        QVERIFY(!guest.isHost());
        QTRY_VERIFY(guestSpy.size() > 0);
        host.send({{"type", "create"}, {"name", "Together"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        host.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "Keep it simple"}});
        guest.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "Make all the sections easy to find"}});
        QTRY_COMPARE(workspace.load(id)["messages"].toArray().size(), 2);
        const auto messages = workspace.load(id)["messages"].toArray();
        QCOMPARE(messages[0].toObject()["author"].toString(), QString("Matt"));
        QCOMPARE(messages[1].toObject()["author"].toString(), QString("Saori"));
        QVERIFY(hostSpy.size() > 1);
        QVERIFY(guestSpy.size() > 1);
    }
    void proposalsNeedEveryContributorAndBecomeStale() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        auto id = workspace.createProject("Agreement", "", &error);
        const auto initial = workspace.source(id);
        auto state = workspace.load(id);
        state["epoch"] = 2;
        state["contributors"] = QJsonArray{"Matt", "Saori"};
        state["proposal"] = QJsonObject{{"id", "p1"}, {"epoch", 2}, {"kind", "proposal"},
            {"message", "A simpler layout"}, {"authors", QJsonArray{"Matt", "Saori"}},
            {"accepted", QJsonArray()}, {"qml", "import QtQuick\nRectangle { width: 520; height: 640 }"}};
        QVERIFY(workspace.save(id, state));
        Session session(dir.path()); session.start();
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", "p1"}});
        QCOMPARE(workspace.source(id), initial);
        QCOMPARE(workspace.load(id)["proposal"].toObject()["accepted"].toArray().size(), 1);
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Visitor"}, {"proposalId", "p1"}});
        QCOMPARE(workspace.load(id)["proposal"].toObject()["accepted"].toArray().size(), 1);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "Actually, try another layout"}});
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Saori"}, {"proposalId", "p1"}});
        QCOMPARE(workspace.source(id), initial);
    }
    void agreedProposalChecksAndUpdatesNativeSource() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Build", "", &error);
        auto state = workspace.load(id);
        const auto source = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'blue' }");
        state["epoch"] = 1;
        state["proposal"] = QJsonObject{{"id", "p1"}, {"epoch", 1}, {"message", "Try blue"},
            {"authors", QJsonArray{"Matt", "Saori"}}, {"accepted", QJsonArray()}, {"qml", source}};
        workspace.save(id, state);
        Session session(dir.path()); session.start();
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", "p1"}});
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Saori"}, {"proposalId", "p1"}});
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["revision"].toInt(), 2, 15000);
        QCOMPARE(workspace.source(id), source);
        QCOMPARE(workspace.load(id)["decisions"].toArray().size(), 1);
    }
    void brokenQmlLeavesTheCurrentAppIntact() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        auto id = workspace.createProject("Broken proposal", "", &error);
        const auto initial = workspace.source(id);
        auto state = workspace.load(id);
        state["epoch"] = 1;
        state["proposal"] = QJsonObject{{"id", "bad"}, {"epoch", 1}, {"message", "Broken"},
            {"authors", QJsonArray{"Matt"}}, {"accepted", QJsonArray()}, {"qml", "this is not QML"}};
        workspace.save(id, state);
        Session session(dir.path()); session.start();
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", "bad"}});
        QTRY_VERIFY_WITH_TIMEOUT(workspace.load(id)["proposal"].toObject().isEmpty(), 15000);
        QCOMPARE(workspace.source(id), initial);
        QCOMPARE(workspace.load(id)["revision"].toInt(), 1);
    }
};

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    CoreTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "tst_core.moc"
