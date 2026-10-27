#include "workspace.h"
#include "session.h"
#include "agent.h"
#include "inkitem.h"
#include "controller.h"
#include "typography.h"
#include "designgrid.h"
#include "svgicon.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QFile>
#include <QDir>
#include <QJsonArray>
#include <QJsonDocument>
#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QScopeGuard>
#include <QStandardPaths>
#include <QFontDatabase>
#include <QFontInfo>
#include <QQmlComponent>
#include <QQmlEngine>

static bool writeAgentReply(const QString &path, const QJsonObject &reply, const QByteArray &before = {}) {
    const auto shell = QStandardPaths::findExecutable("sh").toUtf8();
    return !shell.isEmpty() && Workspace::writeFile(path, "#!" + shell + "\ncat >/dev/null\n" + before
        + "cat <<'CENTAUR_REPLY'\n" + QJsonDocument(reply).toJson(QJsonDocument::Compact) + "\nCENTAUR_REPLY\n")
        && QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
}

static bool writeAgentEvents(const QString &path, const QJsonArray &events) {
    const auto shell = QStandardPaths::findExecutable("sh").toUtf8();
    QByteArray stream;
    for (const auto &event : events) stream += QJsonDocument(event.toObject()).toJson(QJsonDocument::Compact) + '\n';
    // Split the first JSON frame across reads, like a real subprocess pipe.
    return !shell.isEmpty() && !stream.isEmpty() && Workspace::writeFile(path, "#!" + shell
        + "\ncat >/dev/null\nprintf '{'\nsleep 0.05\ncat <<'CENTAUR_EVENTS'\n" + stream.mid(1)
        + "CENTAUR_EVENTS\n")
        && QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
}

class AgentOverride {
public:
    explicit AgentOverride(const QString &path) : m_hadValue(qEnvironmentVariableIsSet("CENTAUR_AGENT")),
        m_previous(qgetenv("CENTAUR_AGENT")) { qputenv("CENTAUR_AGENT", path.toUtf8()); }
    ~AgentOverride() {
        if (m_hadValue) qputenv("CENTAUR_AGENT", m_previous);
        else qunsetenv("CENTAUR_AGENT");
    }
private:
    bool m_hadValue;
    QByteArray m_previous;
};

class CoreTests : public QObject {
    Q_OBJECT
private slots:
    void initTestCase() { Q_INIT_RESOURCE(starter); }
    void projectCardActionsPreserveIdentityAndUpdateOtherWindows() {
        QTemporaryDir dir;
        Controller host(dir.path()); host.start(); host.setAuthor("Matt");
        host.createProject("Family board", "Our app");
        const auto id = host.projectId();
        QVERIFY(!id.isEmpty());
        Workspace workspace(dir.path());
        const auto source = workspace.source(id);
        const auto history = workspace.history(id);
        host.sendMessage("Keep this conversation");
        host.createProject("Another app", "");
        const auto other = host.projectId();
        host.openProject(id);
        Controller guest(dir.path()); guest.start(); guest.setAuthor("Saori");
        QTRY_COMPARE(guest.projects().size(), 2);
        guest.openProject(id);
        guest.renameProject(id, "  Family Planner  ");
        QTRY_COMPARE(host.project().value("name").toString(), QString("Family Planner"));
        QTRY_COMPARE(guest.project().value("name").toString(), QString("Family Planner"));
        QCOMPARE(host.projectId(), id);
        QCOMPARE(workspace.projects().size(), 2);
        QCOMPARE(workspace.source(id), source);
        QCOMPARE(workspace.history(id), history);
        QCOMPARE(workspace.load(id)["messages"].toArray().size(), 1);
        QSignalSpy errors(&host, &Controller::error);
        host.renameProject(id, "   ");
        host.renameProject(id, QString(101, 'x'));
        QCOMPARE(errors.size(), 2);
        QCOMPARE(workspace.load(id)["name"].toString(), QString("Family Planner"));
        host.deleteProject("../projects");
        QCOMPARE(errors.size(), 3);
        QCOMPARE(workspace.projects().size(), 2);
        guest.deleteProject(id);
        QTRY_VERIFY(host.projectId().isEmpty());
        QTRY_VERIFY(guest.projectId().isEmpty());
        QTRY_COMPARE(guest.projects().size(), 1);
        QCOMPARE(workspace.projects().size(), 1);
        QVERIFY(!QFileInfo::exists(workspace.projectPath(id)));
        QVERIFY(QFileInfo::exists(workspace.projectPath(other) + "/App.qml"));
        QVERIFY(QFileInfo::exists(dir.path() + "/trash/" + id + "/.centaur/state.json"));
        host.deleteProject(id); // Stale menus must not affect another project.
        QCOMPARE(errors.size(), 4);
        QCOMPARE(workspace.projects().size(), 1);
    }
    void gridAndIdentityPreferencesPersist() {
        QTemporaryDir dir;
        {
            Controller controller(dir.path());
            QCOMPARE(controller.gridSize(), 8);
            QCOMPARE(controller.gridOpacity(), 50);
            QCOMPARE(controller.gridColor(), QColor("#BAE6FF"));
            QVERIFY(!controller.gridEnabled());
            controller.setAuthor("Matt");
            controller.setGridSize(12); controller.setGridOpacity(70);
            controller.setGridColor(QColor("#aabbcc")); controller.setGridEnabled(true);
        }
        Controller reopened(dir.path());
        if (!qEnvironmentVariableIsSet("CENTAUR_AUTHOR")) QCOMPARE(reopened.author(), QString("Matt"));
        QCOMPARE(reopened.gridSize(), 12); QCOMPARE(reopened.gridOpacity(), 70);
        QCOMPARE(reopened.gridColor(), QColor("#aabbcc")); QVERIFY(reopened.gridEnabled());
        reopened.setGridSize(0); QCOMPARE(reopened.gridSize(), 2);
        reopened.setGridSize(100); QCOMPARE(reopened.gridSize(), 64);
        reopened.setGridOpacity(-1); QCOMPARE(reopened.gridOpacity(), 0);
        reopened.setGridOpacity(101); QCOMPARE(reopened.gridOpacity(), 100);
        reopened.setGridColor(QColor()); QCOMPARE(reopened.gridColor(), QColor("#aabbcc"));
    }
    void gridAndOriginalSvgDoNotInterceptInput() {
        DesignGrid grid;
        grid.setSize(QSizeF(24, 24)); grid.setOrigin(QPointF(3, 5));
        QCOMPARE(grid.acceptedMouseButtons(), Qt::NoButton);
        QImage image(24, 24, QImage::Format_ARGB32_Premultiplied); image.fill(Qt::transparent);
        QPainter painter(&image); grid.paint(&painter); painter.end();
        QCOMPARE(image.pixelColor(0, 0).alpha(), 0);
        QCOMPARE(image.pixelColor(3, 0), grid.color());
        QCOMPARE(image.pixelColor(0, 5), grid.color());
        SvgIcon icon;
        icon.setSize(QSizeF(32, 32)); icon.setSource(QUrl("qrc:/assets/dialogue/project-icon-default.svg"));
        icon.setColor(QColor("#6b6b6b"));
        QCOMPARE(icon.acceptedMouseButtons(), Qt::NoButton);
        QImage rendered(32, 32, QImage::Format_ARGB32_Premultiplied); rendered.fill(Qt::transparent);
        QPainter svgPainter(&rendered); icon.paint(&svgPainter); svgPainter.end();
        QCOMPARE(rendered.pixelColor(0, 0).alpha(), 0);
        bool found = false;
        for (int y = 0; y < 32; ++y) for (int x = 0; x < 32; ++x) if (rendered.pixelColor(x, y).alpha() > 200) {
            const auto color = rendered.pixelColor(x, y);
            QCOMPARE(color.red(), 107); QCOMPARE(color.green(), 107); QCOMPARE(color.blue(), 107); found = true;
        }
        QVERIFY(found);
    }
    void interRendersTextAndControlsWithoutSystemInstallation() {
        QCOMPARE(QGuiApplication::font().family(), QString("Inter"));
        for (auto weight : {QFont::Normal, QFont::DemiBold, QFont::Bold}) {
            QFont font("Inter"); font.setWeight(weight);
            const QFontInfo resolved(font);
            QCOMPARE(resolved.family(), QString("Inter"));
            QCOMPARE(resolved.weight(), weight);
        }
        QQmlEngine engine;
        QQmlComponent component(&engine);
        component.setData("import QtQuick\nimport QtQuick.Controls.Basic\nItem {\n"
            "Text { objectName: 'heading'; text: 'Family planner'; font.weight: Font.DemiBold; "
                "property string renderedFamily: fontInfo.family }\n"
            "TextEdit { objectName: 'chat'; text: 'Hello family'; font.pointSize: 12.5 }\n"
            "Button { objectName: 'button'; text: 'Add' }\n"
            "TextField { objectName: 'field'; placeholderText: 'Add a task' }\n"
            "CheckBox { objectName: 'checkbox'; text: 'Plan something' }\n}", QUrl("qrc:/font-check.qml"));
        QScopedPointer<QObject> root(component.create());
        QVERIFY2(root, qPrintable(component.errorString()));
        for (const auto *name : {"heading", "chat", "button", "field", "checkbox"}) {
            const auto item = root->findChild<QObject *>(QString::fromLatin1(name));
            QVERIFY(item);
            QCOMPARE(QFontInfo(qvariant_cast<QFont>(item->property("font"))).family(), QString("Inter"));
        }
        QCOMPARE(root->findChild<QObject *>("heading")->property("renderedFamily").toString(), QString("Inter"));
        QVERIFY(!QFontDatabase::styles("Inter").isEmpty());
    }
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
    void starterWindowsReuseOneProject_data() {
        QTest::addColumn<bool>("existingProject");
        QTest::newRow("new workspace") << false;
        QTest::newRow("existing project") << true;
    }
    void starterWindowsReuseOneProject() {
        QFETCH(bool, existingProject);
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString id;
        {
            Controller host(dir.path()); host.start();
            if (existingProject) {
                host.createProject("Family planner", "An existing app");
                id = host.projectId();
                QVERIFY(!id.isEmpty());
            }
            Controller firstGuest(dir.path()); firstGuest.start();
            Controller secondGuest(dir.path()); secondGuest.start();
            // Match main(): --demo runs before guests receive their first list.
            QVERIFY(firstGuest.projects().isEmpty());
            QVERIFY(secondGuest.projects().isEmpty());
            firstGuest.openStarterProject();
            secondGuest.openStarterProject();
            host.openStarterProject();
            if (id.isEmpty()) id = host.projectId();
            QVERIFY(!id.isEmpty());
            QTRY_COMPARE(firstGuest.projectId(), id);
            QTRY_COMPARE(secondGuest.projectId(), id);
            QCOMPARE(host.projects().size(), 1);
            QCOMPARE(firstGuest.projects().size(), 1);
            QCOMPARE(secondGuest.projects().size(), 1);
            QCOMPARE(workspace.projects().size(), 1);
            QCOMPARE(workspace.projects().first().toMap()["id"].toString(), id);
            host.closeProject();
            host.openStarterProject();
            QCOMPARE(host.projectId(), id);
        }
        Controller reopened(dir.path()); reopened.start(); reopened.openStarterProject();
        QCOMPARE(reopened.projectId(), id);
        QCOMPARE(workspace.projects().size(), 1);
        // Explicitly creating a different project remains available.
        reopened.createProject("Another app", "");
        QVERIFY(reopened.projectId() != id);
        QCOMPARE(workspace.projects().size(), 2);
    }
    void savedHistoryPreservesExactSources() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("History", "", &error);
        QVERIFY2(!id.isEmpty(), qPrintable(error));
        const auto initial = workspace.source(id);
        const auto first = workspace.history(id, &error);
        QCOMPARE(first.size(), 1);
        const auto initialCheckpoint = first.first().toObject()["checkpoint"].toString();
        const auto blue = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'blue' }\n");
        QVERIFY(workspace.applySource(id, blue, "Make the background blue", &error));
        const auto history = workspace.history(id, &error);
        QCOMPARE(history.size(), 2);
        QCOMPARE(history.first().toObject()["summary"].toString(), QString("Make the background blue"));
        QVERIFY(!history.first().toObject()["time"].toString().isEmpty());
        QCOMPARE(workspace.sourceAt(id, initialCheckpoint, &error), initial);
        QCOMPARE(workspace.sourceAt(id, history.first().toObject()["checkpoint"].toString(), &error), blue);
        QVERIFY(workspace.sourceAt(id, "HEAD~1:../../outside", &error).isEmpty());
        const auto other = workspace.createProject("Other project", "", &error);
        const auto foreignCheckpoint = workspace.history(other).first().toObject()["checkpoint"].toString();
        QVERIFY(workspace.sourceAt(id, foreignCheckpoint, &error).isEmpty());
        QCOMPARE(workspace.source(id), blue);
    }
    void agentResponsesAreValidated() {
        QString error;
        QVERIFY(Agent::parseReply("not json", &error).isEmpty());
        QVERIFY(Agent::parseReply(R"({"kind":"proposal","message":"Done"})", &error).isEmpty());
        QVERIFY(Agent::parseReply(R"({"kind":"anything","message":"Done"})", &error).isEmpty());
        const QJsonObject compatible{{"kind", "proposal"}, {"message", "Try blue"},
            {"conflict", QJsonValue::Null}, {"qml", "import QtQuick\nRectangle { color: 'blue' }"}};
        QVERIFY(!Agent::parseReply(QJsonDocument(compatible).toJson(), &error).isEmpty());
        auto missingClassification = compatible;
        missingClassification.remove("conflict");
        QVERIFY(Agent::parseReply(QJsonDocument(missingClassification).toJson(), &error).isEmpty());
        QJsonObject restore{{"kind", "restore"}, {"message", "Return to the blue background"},
            {"checkpoint", QString(40, 'a')}, {"conflict", QJsonValue::Null}};
        QVERIFY(!Agent::parseReply(QJsonDocument(restore).toJson(), &error).isEmpty());
        restore["checkpoint"] = "HEAD~1";
        QVERIFY(Agent::parseReply(QJsonDocument(restore).toJson(), &error).isEmpty());
        auto conflict = compatible;
        conflict["conflict"] = QJsonObject{{"reason", "Show all tasks versus hide completed tasks"},
            {"authors", QJsonArray{"Matt", "Saori"}}};
        QVERIFY(!Agent::parseReply(QJsonDocument(conflict).toJson(), &error).isEmpty());
        for (const auto &invalid : QJsonArray{
                 true, QJsonObject(),
                 QJsonObject{{"reason", "Opposing requests"}, {"authors", QJsonArray{"Matt"}}},
                 QJsonObject{{"reason", "Opposing requests"}, {"authors", QJsonArray{"Matt", "Matt"}}},
                 QJsonObject{{"reason", ""}, {"authors", QJsonArray{"Matt", "Saori"}}}}) {
            conflict["conflict"] = invalid;
            QVERIFY(Agent::parseReply(QJsonDocument(conflict).toJson(), &error).isEmpty());
        }
        QCOMPARE(Agent::parseReply("```json\n{\"kind\":\"question\",\"message\":\"Which is better?\"}\n```", &error)["kind"].toString(), QString("question"));
    }
    void agentReceivesStdinEofBeforeReplying() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Agent connection", "", &error);
        QVERIFY2(!id.isEmpty(), qPrintable(error));
        const auto fake = dir.path() + "/stdin-agent";
        const auto shell = QStandardPaths::findExecutable("sh").toUtf8();
        QVERIFY(!shell.isEmpty());
        // Like omp's print mode, consume piped stdin before handling argv.
        QVERIFY(Workspace::writeFile(fake, "#!" + shell + "\ncat >/dev/null\n"
            "printf '%s\\n' '{\"kind\":\"question\",\"message\":\"Connection test\"}'\n"));
        QVERIFY(QFile::setPermissions(fake, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        const bool hadAgent = qEnvironmentVariableIsSet("CENTAUR_AGENT");
        const auto previousAgent = qgetenv("CENTAUR_AGENT");
        const auto restoreAgent = qScopeGuard([&] {
            if (hadAgent) qputenv("CENTAUR_AGENT", previousAgent);
            else qunsetenv("CENTAUR_AGENT");
        });
        qputenv("CENTAUR_AGENT", fake.toUtf8());
        Agent agent;
        QSignalSpy completed(&agent, &Agent::completed);
        QSignalSpy failed(&agent, &Agent::failed);
        const auto stopAgent = qScopeGuard([&] { agent.cancel(); });
        // A reused QProcess must provide EOF on every request, not only the first.
        for (int request = 1; request <= 2; ++request) {
            agent.ask(workspace.projectPath(id), workspace.load(id), workspace.source(id));
            QTRY_COMPARE_WITH_TIMEOUT(completed.size(), request, 3000);
            QVERIFY(failed.isEmpty());
            QCOMPARE(completed.last().first().toJsonObject()["message"].toString(), QString("Connection test"));
            QVERIFY(!agent.busy());
        }
    }
    void structuredAgentOutputReportsTheActualModelAndFinalReply_data() {
        QTest::addColumn<QJsonObject>("reply");
        QTest::newRow("question") << QJsonObject{{"kind", "question"}, {"message", "Connection test"}};
        QTest::newRow("proposal with escaped QML") << QJsonObject{{"kind", "proposal"},
            {"message", "Change the title."}, {"conflict", QJsonValue::Null},
            {"qml", "import QtQuick\nRectangle { Text { text: \"Family Planner\" } }\n"}};
    }
    void structuredAgentOutputReportsTheActualModelAndFinalReply() {
        QFETCH(QJsonObject, reply);
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Structured agent", "", &error);
        QVERIFY2(!id.isEmpty(), qPrintable(error));
        const auto fake = dir.path() + "/event-agent";
        const auto replyText = QString::fromUtf8(QJsonDocument(reply).toJson(QJsonDocument::Compact));
        const QJsonObject first{{"role", "assistant"}, {"provider", "initial-provider"}, {"model", "initial-model"},
            {"stopReason", "error"}, {"content", QJsonArray()}};
        const QJsonObject final{{"role", "assistant"}, {"provider", "actual-provider"}, {"model", "actual-model"},
            {"stopReason", "stop"}, {"content", QJsonArray{
                QJsonObject{{"type", "thinking"}, {"thinking", "This must not appear in the reply."}},
                QJsonObject{{"type", "text"}, {"text", replyText}}}}};
        QVERIFY(writeAgentEvents(fake, {
            QJsonObject{{"type", "session"}},
            QJsonObject{{"type", "message_start"}, {"message", QJsonObject{{"role", "user"}, {"provider", "ignore"}, {"model", "ignore"}}}},
            QJsonObject{{"type", "message_start"}, {"message", first}},
            QJsonObject{{"type", "message_end"}, {"message", first}},
            QJsonObject{{"type", "message_start"}, {"message", final}},
            QJsonObject{{"type", "message_update"}, {"assistantMessageEvent", QJsonObject{{"type", "text_delta"}, {"delta", "partial"}}}},
            QJsonObject{{"type", "message_end"}, {"message", final}},
            QJsonObject{{"type", "agent_end"}, {"messages", QJsonArray{first, final}}}}));
        const AgentOverride agentOverride(fake);
        Agent agent;
        QSignalSpy completed(&agent, &Agent::completed);
        QSignalSpy failed(&agent, &Agent::failed);
        QSignalSpy models(&agent, &Agent::modelReported);
        agent.ask(workspace.projectPath(id), workspace.load(id), workspace.source(id));
        QTRY_COMPARE_WITH_TIMEOUT(completed.size(), 1, 5000);
        QVERIFY(failed.isEmpty());
        QCOMPARE(completed.first().first().toJsonObject(), reply);
        QCOMPARE(models.size(), 2);
        QCOMPARE(models.last().first().toString(), QString("actual-provider/actual-model"));
    }
    void modelMetadataIsSharedBetweenNativeWindows() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/model-agent";
        const QJsonObject message{{"role", "assistant"}, {"provider", "provider"}, {"model", "resolved-model"},
            {"content", QJsonArray{QJsonObject{{"type", "text"},
                {"text", "{\"kind\":\"question\",\"message\":\"Hello\"}"}}}}};
        QVERIFY(writeAgentEvents(fake, {QJsonObject{{"type", "message_end"}, {"message", message}}}));
        const AgentOverride agentOverride(fake);
        Controller host(dir.path()); host.start(); host.setAuthor("Matt");
        host.createProject("Model metadata", "");
        QVERIFY(!host.projectId().isEmpty());
        Controller guest(dir.path()); guest.start();
        QTRY_VERIFY(!guest.projects().isEmpty());
        guest.openProject(host.projectId());
        QVERIFY(guest.agentModel().isEmpty());
        host.sendMessage("@centaur hello");
        QTRY_COMPARE_WITH_TIMEOUT(host.agentModel(), QString("provider/resolved-model"), 5000);
        QTRY_COMPARE(guest.agentModel(), host.agentModel());
        host.renameAgent("merlin");
        QTRY_COMPARE(guest.project().value("agentName").toString(), QString("merlin"));
        Workspace workspace(dir.path());
        QTRY_COMPARE(workspace.load(host.projectId())["messages"].toArray().size(), 2);
        QCOMPARE(workspace.load(host.projectId())["agentModel"].toString(), host.agentModel());
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
    void compatibleRequestsApplyWithoutApproval() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/fake-agent";
        const auto qml = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'green' }");
        const QJsonObject reply{{"kind", "proposal"}, {"conflict", QJsonValue::Null},
            {"message", "Keep navigation short, with every section reachable."},
            {"qml", qml}};
        QVERIFY(writeAgentReply(fake, reply));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        QSignalSpy sourceChanged(&session, &Session::sourceChanged);
        Session guest(dir.path());
        QSignalSpy guestSnapshots(&guest, &Session::snapshot);
        guest.start();
        QTRY_VERIFY(!guestSnapshots.isEmpty());
        session.send({{"type", "create"}, {"name", "Negotiate"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "Keep navigation simple"}});
        guest.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "@centaur keep every section easy to reach"}});
        // No accept command from either author: making the request approves it.
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["revision"].toInt(), 2, 15000);
        QCOMPARE(workspace.source(id), qml);
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
        QCOMPARE(workspace.projects().size(), 1);
        QCOMPARE(workspace.projects().first().toMap()["id"].toString(), id);
        const auto decision = workspace.load(id)["decisions"].toArray().last().toObject();
        QCOMPARE(decision["authors"].toArray(), QJsonArray{"Saori"});
        QCOMPARE(decision["requestedBy"].toString(), QString("Saori"));
        QVERIFY(decision["conflict"].isNull());
        QCOMPARE(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString(), QString("Updated the app."));
        QCOMPARE(sourceChanged.size(), 1);
        QTRY_COMPARE(guestSnapshots.last().first().toJsonObject()["states"].toArray().first().toObject()["revision"].toInt(), 2);
    }
    void conflictingRequestsNeedOnlyAffectedAuthors() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/conflict-agent";
        const QJsonObject conflict{{"reason", "Matt wants all tasks visible; Saori wants completed tasks hidden."},
            {"authors", QJsonArray{"Matt", "Saori"}}};
        const auto qml = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'blue' }");
        QVERIFY(writeAgentReply(fake, {{"kind", "proposal"}, {"message", "Add a toggle for completed tasks."},
            {"conflict", conflict}, {"qml", qml}}));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        session.send({{"type", "create"}, {"name", "Compromise"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        const auto initial = workspace.source(id);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Sam"}, {"text", "The title looks good."}});
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "Keep every task visible."}});
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "@centaur hide completed tasks."}});
        QTRY_VERIFY_WITH_TIMEOUT(!workspace.load(id)["proposal"].toObject().isEmpty(), 5000);
        const auto proposal = workspace.load(id)["proposal"].toObject();
        QCOMPARE(proposal["authors"].toArray(), (QJsonArray{"Matt", "Saori"}));
        QVERIFY(proposal["accepted"].toArray().isEmpty());
        QCOMPARE(proposal["conflict"].toObject(), conflict);
        QCOMPARE(workspace.source(id), initial);
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Sam"}, {"proposalId", proposal["id"]}});
        QVERIFY(workspace.load(id)["proposal"].toObject()["accepted"].toArray().isEmpty());
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", proposal["id"]}});
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", proposal["id"]}});
        QCOMPARE(workspace.source(id), initial);
        QCOMPARE(workspace.load(id)["proposal"].toObject()["accepted"].toArray(), QJsonArray{"Matt"});
        session.send({{"type", "accept"}, {"projectId", id}, {"author", "Saori"}, {"proposalId", proposal["id"]}});
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["revision"].toInt(), 2, 15000);
        QCOMPARE(workspace.source(id), qml);
        const auto decision = workspace.load(id)["decisions"].toArray().last().toObject();
        QCOMPARE(decision["authors"].toArray(), (QJsonArray{"Matt", "Saori"}));
        QCOMPARE(decision["conflict"].toObject(), conflict);
    }
    void conflictCannotRequireAnUnknownAuthorsAgreement() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/unknown-author-agent";
        QVERIFY(writeAgentReply(fake, {{"kind", "proposal"}, {"message", "A compromise"},
            {"conflict", QJsonObject{{"reason", "Opposing requests"}, {"authors", QJsonArray{"Matt", "Nobody"}}}},
            {"qml", "import QtQuick\nRectangle { color: 'blue' }"}}));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        session.send({{"type", "create"}, {"name", "Unknown author"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        const auto initial = workspace.source(id);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "@centaur make it blue"}});
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["messages"].toArray().size(), 2, 5000);
        QVERIFY(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString().contains("couldn't identify"));
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
        QCOMPARE(workspace.source(id), initial);
        QCOMPARE(workspace.load(id)["revision"].toInt(), 1);
    }
    void newDiscussionInvalidatesAnInFlightAgentReply() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/slow-agent";
        const auto reply = QJsonDocument(QJsonObject{{"kind", "proposal"}, {"message", "Try blue"}, {"conflict", QJsonValue::Null},
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
    void newDiscussionDuringAutomaticCheckDoesNotApplyStaleCode() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/agent";
        QVERIFY(writeAgentReply(fake, {{"kind", "proposal"}, {"message", "Try blue"},
            {"conflict", QJsonValue::Null}, {"qml", "import QtQuick\nRectangle { color: 'blue' }"}}));
        const AgentOverride agentOverride(fake);
        const auto checker = dir.path() + "/checker";
        const auto shell = QStandardPaths::findExecutable("sh").toUtf8();
        QVERIFY(!shell.isEmpty());
        QVERIFY(Workspace::writeFile(checker, "#!" + shell + "\n: > \"$2.checking\"\nsleep 0.3\nexit 0\n"));
        QVERIFY(QFile::setPermissions(checker, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        const bool hadPreview = qEnvironmentVariableIsSet("CENTAUR_PREVIEW");
        const auto previousPreview = qgetenv("CENTAUR_PREVIEW");
        const auto restorePreview = qScopeGuard([&] {
            if (hadPreview) qputenv("CENTAUR_PREVIEW", previousPreview);
            else qunsetenv("CENTAUR_PREVIEW");
        });
        qputenv("CENTAUR_PREVIEW", checker.toUtf8());
        Session session(dir.path()); session.start();
        session.send({{"type", "create"}, {"name", "Correction during check"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        const auto initial = workspace.source(id);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "@centaur make it blue"}});
        QTRY_VERIFY_WITH_TIMEOUT(QFile::exists(workspace.projectPath(id) + "/.centaur/candidate.qml.checking"), 5000);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "Wait, let's discuss the colour."}});
        QTRY_VERIFY_WITH_TIMEOUT(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString().contains("conversation changed while"), 5000);
        QCOMPARE(workspace.source(id), initial);
        QCOMPARE(workspace.load(id)["revision"].toInt(), 1);
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
    }
    void conflictAgreementsBecomeStale() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        auto id = workspace.createProject("Agreement", "", &error);
        const auto initial = workspace.source(id);
        auto state = workspace.load(id);
        state["epoch"] = 2;
        state["contributors"] = QJsonArray{"Matt", "Saori"};
        state["proposal"] = QJsonObject{{"id", "p1"}, {"epoch", 2}, {"kind", "proposal"},
            {"conflict", QJsonObject{{"reason", "Opposing navigation requests"}, {"authors", QJsonArray{"Matt", "Saori"}}}},
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
    void conflictAgreementSurvivesRestartAndUpdatesNativeSource() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Build", "", &error);
        auto state = workspace.load(id);
        const auto source = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'blue' }");
        state["epoch"] = 1;
        state["proposal"] = QJsonObject{{"id", "p1"}, {"epoch", 1}, {"message", "Try blue"},
            {"conflict", QJsonObject{{"reason", "Opposing colour requests"}, {"authors", QJsonArray{"Matt", "Saori"}}}},
            {"authors", QJsonArray{"Matt", "Saori"}}, {"accepted", QJsonArray()}, {"qml", source}};
        workspace.save(id, state);
        {
            Session session(dir.path()); session.start();
            session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", "p1"}});
        }
        Session reopened(dir.path()); reopened.start();
        QCOMPARE(workspace.load(id)["proposal"].toObject()["accepted"].toArray(), QJsonArray{"Matt"});
        reopened.send({{"type", "accept"}, {"projectId", id}, {"author", "Saori"}, {"proposalId", "p1"}});
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["revision"].toInt(), 2, 15000);
        QCOMPARE(workspace.source(id), source);
        QCOMPARE(workspace.load(id)["decisions"].toArray().size(), 1);
    }
    void brokenQmlLeavesTheCurrentAppIntact() {
        QTemporaryDir dir;
        const auto fake = dir.path() + "/broken-qml-agent";
        QVERIFY(writeAgentReply(fake, {{"kind", "proposal"}, {"message", "Try blue"},
            {"conflict", QJsonValue::Null}, {"qml", "this is not QML"}}));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        session.send({{"type", "create"}, {"name", "Broken proposal"}});
        Workspace workspace(dir.path());
        const auto id = workspace.projects().first().toMap()["id"].toString();
        const auto initial = workspace.source(id);
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "@centaur make it blue"}});
        QTRY_VERIFY_WITH_TIMEOUT(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString().contains("did not pass"), 15000);
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
        QCOMPARE(workspace.source(id), initial);
        QCOMPARE(workspace.load(id)["revision"].toInt(), 1);
    }
    void oldApprovalProposalsAreNotSilentlyAppliedOnRestart() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Older proposal", "", &error);
        const auto initial = workspace.source(id);
        auto state = workspace.load(id);
        state["proposal"] = QJsonObject{{"id", "old"}, {"epoch", 0}, {"message", "Try blue"},
            {"authors", QJsonArray{"Matt", "Saori"}}, {"accepted", QJsonArray()},
            {"qml", "import QtQuick\nRectangle { color: 'blue' }"}};
        QVERIFY(workspace.save(id, state));
        Session session(dir.path()); session.start();
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
        QCOMPARE(workspace.source(id), initial);
        QVERIFY(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString().contains("Ask me again"));
    }
    void agentCanAnswerHistoryQuestionsWithoutChangingTheApp() {
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("History question", "", &error);
        const auto source = QString("import QtQuick\nRectangle { color: 'blue' }");
        QVERIFY(workspace.applySource(id, source, "Make the background blue", &error));
        const auto checkpoint = workspace.history(id).first().toObject()["checkpoint"].toString();
        const auto fake = dir.path() + "/history-agent";
        QVERIFY(writeAgentReply(fake, {{"kind", "question"}, {"message", "The background was changed to blue."}}, "sleep 0.2\n"));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "@centaur what changed earlier?"}});
        const auto requests = QDir(workspace.projectPath(id) + "/.centaur").entryList({"request-*.txt"}, QDir::Files);
        QCOMPARE(requests.size(), 1);
        QFile request(workspace.projectPath(id) + "/.centaur/" + requests.first());
        QVERIFY(request.open(QIODevice::ReadOnly));
        const auto prompt = request.readAll();
        QVERIFY(prompt.contains("appHistory"));
        QVERIFY(prompt.contains(checkpoint.toUtf8()));
        QVERIFY(prompt.contains("Make the background blue"));
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["messages"].toArray().size(), 2, 5000);
        QCOMPARE(workspace.source(id), source);
        QCOMPARE(workspace.history(id).size(), 2);
    }
    void rewindsRestoreExactSourceAndKeepLaterHistory_data() {
        QTest::addColumn<bool>("conflicting");
        QTest::newRow("ordinary rewind") << false;
        QTest::newRow("conflicting rewind") << true;
    }
    void rewindsRestoreExactSourceAndKeepLaterHistory() {
        QFETCH(bool, conflicting);
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Rewind", "", &error);
        const auto blue = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'blue' }\n");
        const auto green = QString("import QtQuick\nRectangle { width: 520; height: 640; color: 'green' }\n");
        QVERIFY(workspace.applySource(id, blue, "Make the background blue", &error));
        const auto checkpoint = workspace.history(id).first().toObject()["checkpoint"].toString();
        QVERIFY(workspace.applySource(id, green, "Try a green background", &error));
        const auto laterCheckpoint = workspace.history(id).first().toObject()["checkpoint"].toString();
        auto state = workspace.load(id);
        state["revision"] = 3;
        QVERIFY(workspace.save(id, state));
        const auto fake = dir.path() + "/rewind-agent";
        const QJsonValue conflict = conflicting
            ? QJsonValue(QJsonObject{{"reason", "Matt wants to keep green; Saori wants the earlier blue background."},
                {"authors", QJsonArray{"Matt", "Saori"}}}) : QJsonValue(QJsonValue::Null);
        QVERIFY(writeAgentReply(fake, {{"kind", "restore"}, {"message", "Return to the blue background."},
            {"conflict", conflict}, {"checkpoint", checkpoint},
            {"qml", "import QtQuick\nRectangle { color: 'red' }"}}));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        if (conflicting) session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "Keep the green background."}});
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Saori"}, {"text", "@centaur go back to the blue background."}});
        if (conflicting) {
            QTRY_VERIFY_WITH_TIMEOUT(!workspace.load(id)["proposal"].toObject().isEmpty(), 5000);
            const auto proposal = workspace.load(id)["proposal"].toObject();
            QCOMPARE(proposal["qml"].toString(), blue);
            QCOMPARE(workspace.source(id), green);
            session.send({{"type", "accept"}, {"projectId", id}, {"author", "Matt"}, {"proposalId", proposal["id"]}});
            QCOMPARE(workspace.source(id), green);
            session.send({{"type", "accept"}, {"projectId", id}, {"author", "Saori"}, {"proposalId", proposal["id"]}});
        }
        QTRY_COMPARE_WITH_TIMEOUT(workspace.load(id)["revision"].toInt(), 4, 15000);
        QCOMPARE(workspace.source(id), blue); // Ignore any QML invented in the restore response.
        QCOMPARE(workspace.sourceAt(id, laterCheckpoint, &error), green); // Rewind adds history; it never resets Git.
        QCOMPARE(workspace.history(id).size(), 4);
        const auto decision = workspace.load(id)["decisions"].toArray().last().toObject();
        QCOMPARE(decision["restoredFrom"].toString(), checkpoint);
        QCOMPARE(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString(), QString("Restored that version of the app."));
    }
    void unavailableOrBrokenSavedAppsDoNotReplaceTheCurrentApp_data() {
        QTest::addColumn<bool>("brokenSource");
        QTest::newRow("missing checkpoint") << false;
        QTest::newRow("historical QML fails validation") << true;
    }
    void unavailableOrBrokenSavedAppsDoNotReplaceTheCurrentApp() {
        QFETCH(bool, brokenSource);
        QTemporaryDir dir;
        Workspace workspace(dir.path());
        QString error;
        const auto id = workspace.createProject("Restore failure", "", &error);
        QString checkpoint(40, '0');
        if (brokenSource) {
            QVERIFY(workspace.applySource(id, "This is not QML", "Broken experiment", &error));
            checkpoint = workspace.history(id).first().toObject()["checkpoint"].toString();
        }
        const auto current = QString("import QtQuick\nRectangle { color: 'green' }");
        QVERIFY(workspace.applySource(id, current, "Working green app", &error));
        const auto historySize = workspace.history(id).size();
        const auto fake = dir.path() + "/restore-agent";
        QVERIFY(writeAgentReply(fake, {{"kind", "restore"}, {"message", "Return to the earlier app."},
            {"conflict", QJsonValue::Null}, {"checkpoint", checkpoint}}));
        const AgentOverride agentOverride(fake);
        Session session(dir.path()); session.start();
        session.send({{"type", "message"}, {"projectId", id}, {"author", "Matt"}, {"text", "@centaur restore the earlier app."}});
        const auto expected = brokenSource ? QString("did not pass") : QString("Could not restore");
        QTRY_VERIFY_WITH_TIMEOUT(workspace.load(id)["messages"].toArray().last().toObject()["text"].toString().contains(expected), 15000);
        QCOMPARE(workspace.source(id), current);
        QCOMPARE(workspace.history(id).size(), historySize);
        QVERIFY(workspace.load(id)["proposal"].toObject().isEmpty());
    }
};

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    if (!initializeTypography()) return 1;
    CoreTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "tst_core.moc"
