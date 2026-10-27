#include "controller.h"
#include "inkitem.h"
#include "typography.h"
#include "svgicon.h"
#include "designgrid.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickStyle>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QDir>
#include <QTimer>
#include <QCommandLineParser>
#include <QMouseEvent>
#include <QFile>

static QQuickItem *findVisualItem(QQuickItem *root, const QString &name) {
    if (root->objectName() == name) return root;
    for (auto *child : root->childItems())
        if (auto *item = findVisualItem(child, name)) return item;
    return nullptr;
}

static bool clickItem(QQuickWindow *window, QQuickItem *item) {
    if (!window || !item || !item->isVisible()) return false;
    const auto position = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
    const QPointF global = window->mapToGlobal(position.toPoint());
    QMouseEvent press(QEvent::MouseButtonPress, position, global, Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QMouseEvent release(QEvent::MouseButtonRelease, position, global, Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QCoreApplication::sendEvent(window, &press);
    QCoreApplication::sendEvent(window, &release);
    return true;
}

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    if (!initializeTypography()) return 1;
    QCoreApplication::setApplicationName("Centaur");
    QCoreApplication::setOrganizationName("Centaur");
    QCoreApplication::setApplicationVersion(CENTAUR_APP_VERSION);
    QQuickStyle::setStyle("Basic");
    Q_INIT_RESOURCE(starter);
    QCommandLineParser parser;
    parser.setApplicationDescription("A native workshop for making apps together.");
    parser.addHelpOption(); parser.addVersionOption();
    parser.addOption({"data-dir", "Project and shared session directory.", "path"});
    parser.addOption({"smoke-test", "Load the native UI and exit (temporary data only)."});
    parser.addOption({"network-embedding-smoke-test", "Verify a shared app received from a separate host renders and accepts input."});
    parser.addOption({"embedding-smoke-test", "Verify that a separate native app maps inside the canvas."});
    parser.addOption({"screenshot", "Save a native UI screenshot and exit.", "path"});
    parser.addOption({"demo", "Create and open a starter project if no projects exist."});
    parser.process(app);
    const bool smoke = parser.isSet("smoke-test");
    const bool networkEmbedding = parser.isSet("network-embedding-smoke-test");
    const bool embeddingTest = parser.isSet("embedding-smoke-test") || networkEmbedding;
    QTemporaryDir temporary, ownerTemporary;
    std::unique_ptr<Controller> networkOwner;
    QString root = parser.value("data-dir");
    if (smoke || embeddingTest) root = temporary.path();
    if (root.isEmpty()) root = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    root = QDir(root).absolutePath();
    Controller controller(root);
    bool inputForwarded = false;
    QObject::connect(&controller, &Controller::previewOutput, &app, [&inputForwarded](const QByteArray &output) {
        if (output.contains("CENTAUR_INPUT_OK")) inputForwarded = true;
    });
    qmlRegisterType<InkItem>("Centaur.Native", 1, 0, "InkLayer");
    qmlRegisterType<SvgIcon>("Centaur.Native", 1, 0, "SvgIcon");
    qmlRegisterType<DesignGrid>("Centaur.Native", 1, 0, "DesignGrid");
    QQmlApplicationEngine engine;
    QObject::connect(&app, &QCoreApplication::aboutToQuit, &app, [&controller] { controller.stopPreview(); });
    engine.rootContext()->setContextProperty("Backend", &controller);
    bool qmlWarning = false;
    QObject::connect(&engine, &QQmlEngine::warnings, &app, [&qmlWarning] { qmlWarning = true; });
    engine.load(QUrl("qrc:/qml/Main.qml"));
    if (engine.rootObjects().isEmpty()) return 1;
    if (embeddingTest && !networkEmbedding) {
        Workspace workspace(root);
        QString error;
        const auto id = workspace.createProject("Embedding test", "Temporary native client probe", &error);
        QFile probe(":/tests/fixtures/EmbeddedProbe.qml");
        if (id.isEmpty() || !probe.open(QIODevice::ReadOnly)
            || !Workspace::writeFile(workspace.projectPath(id) + "/App.qml", probe.readAll())) return 1;
    }
    controller.start(!smoke && !embeddingTest);
    if ((embeddingTest && !networkEmbedding) || parser.isSet("demo")) controller.openStarterProject();
    if (networkEmbedding) {
        qputenv("CENTAUR_PORT", "0");
        networkOwner = std::make_unique<Controller>(ownerTemporary.path());
        auto *owner = networkOwner.get();
        auto prepared = std::make_shared<bool>(false), joining = std::make_shared<bool>(false);
        QObject::connect(owner, &Controller::changed, &app, [&, owner, prepared, joining] {
            if (!owner->projectId().isEmpty() && !*prepared) {
                *prepared = true;
                QFile probe(":/tests/fixtures/EmbeddedProbe.qml");
                if (!probe.open(QIODevice::ReadOnly) || !Workspace::writeFile(ownerTemporary.path() + "/projects/" + owner->projectId() + "/App.qml", probe.readAll())) { app.exit(1); return; }
                owner->invitePeople("127.0.0.1");
            }
            if (!owner->invitationCode().isEmpty() && !*joining) { *joining = true; controller.joinProject(owner->invitationCode(), "Remote tester"); }
        });
        QObject::connect(&app, &QCoreApplication::aboutToQuit, &app, [&] {
            QProcess::execute(QCoreApplication::applicationDirPath() + "/centaur-host", {"--stop", "--data-dir", ownerTemporary.path()});
        });
        owner->start(true); owner->setAuthor("Host"); owner->createProject("Network embedding", "Native app over TLS");
    }
    const auto saveSmokeImage = [&](const QString &name) {
        if (!parser.isSet("screenshot")) return;
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        auto path = parser.value("screenshot");
        const auto dot = path.lastIndexOf('.');
        path.insert(dot >= 0 ? dot : path.size(), "-" + name);
        if (dot < 0) path += ".png";
        if (!window || !window->grabWindow().save(path)) qmlWarning = true;
    };
    if (smoke) {
        QTimer::singleShot(50, &app, [&] { saveSmokeImage("projects"); });
        // Exercise both main views and all their QML components.
        QTimer::singleShot(100, &app, [&] {
            controller.createProject("UI test", "Temporary smoke-test project");
            controller.setAuthor("Matt"); controller.sendMessage("Let's make something simple.");
            controller.setAuthor("Saori"); controller.sendMessage("And easy for everyone to use.");
            controller.addAnnotation({{"tool", "draw"}, {"points", QVariantList{
                QVariantMap{{"x", 0.1}, {"y", 0.2}}, QVariantMap{{"x", 0.2}, {"y", 0.3}}}}});
        });
        QTimer::singleShot(300, &app, [&] {
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            window->setProperty("buildMode", true);
            controller.setGridEnabled(true);
        });
        QTimer::singleShot(450, &app, [&] {
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            auto *chat = window->findChild<QQuickItem *>("chatComposer");
            auto *ink = window->findChild<InkItem *>("inkLayer");
            if (!chat || !chat->isVisible() || !ink || ink->acceptedMouseButtons() != Qt::LeftButton) qmlWarning = true;
            saveSmokeImage("build");
            window->setProperty("buildMode", false);
        });
        QTimer::singleShot(550, &app, [&] {
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            auto *chat = window->findChild<QQuickItem *>("chatComposer");
            auto *ink = window->findChild<InkItem *>("inkLayer");
            if (!chat || !chat->isVisible() || !ink || ink->acceptedMouseButtons() != Qt::NoButton) qmlWarning = true;
            saveSmokeImage("interact");
            window->setProperty("page", "designSystems");
        });
        QTimer::singleShot(750, &app, [&] { saveSmokeImage("design-systems"); engine.rootObjects().first()->setProperty("page", "settings"); });
        QTimer::singleShot(950, &app, [&] { saveSmokeImage("settings"); engine.rootObjects().first()->setProperty("page", "projects"); });
        // Use actual pointer events: a card's menu must not also open the card.
        const auto click = [&](const char *name) {
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            if (!clickItem(window, findVisualItem(window->contentItem(), QString::fromUtf8(name)))) { qCritical("Smoke test could not click %s", name); qmlWarning = true; }
        };
        QTimer::singleShot(1000, &app, [&] { controller.closeProject(); });
        QTimer::singleShot(1150, &app, [&, click] { click("projectMenuButton"); });
        QTimer::singleShot(1300, &app, [&, click] {
            if (!controller.projectId().isEmpty()) { qCritical("Card menu also opened the project"); qmlWarning = true; }
            saveSmokeImage("project-menu");
            click("projectMenuEntry-Rename");
        });
        QTimer::singleShot(1450, &app, [&] {
            auto *dialog = engine.rootObjects().first()->findChild<QObject *>("renameProjectDialog");
            auto *field = engine.rootObjects().first()->findChild<QObject *>("renameProjectName");
            if (!dialog || !dialog->property("visible").toBool() || !field) { qCritical("Rename dialog did not open"); qmlWarning = true; return; }
            field->setProperty("text", "Renamed UI test");
            QMetaObject::invokeMethod(field, "accepted");
        });
        QTimer::singleShot(1600, &app, [&, click] {
            if (controller.projects().size() != 1 || controller.projects().first().toMap()["name"] != "Renamed UI test") { qCritical("Rename did not update the project card"); qmlWarning = true; }
            click("projectMenuButton");
        });
        QTimer::singleShot(1750, &app, [&, click] { click("projectMenuEntry-Delete"); });
        QTimer::singleShot(1900, &app, [&, click] { saveSmokeImage("delete-confirmation"); click("cancelProjectDeletion"); });
        QTimer::singleShot(2050, &app, [&, click] {
            if (controller.projects().size() != 1) { qCritical("Cancel deleted the project"); qmlWarning = true; }
            click("projectMenuButton");
        });
        QTimer::singleShot(2200, &app, [&, click] { click("projectMenuEntry-Delete"); });
        QTimer::singleShot(2350, &app, [&, click] { click("confirmProjectDeletion"); });
        QTimer::singleShot(2500, &app, [&] {
            if (!controller.projects().isEmpty()) qmlWarning = true;
            auto *dialogs = engine.rootObjects().first()->findChild<QObject *>("collaborationDialogs");
            if (!dialogs || !QMetaObject::invokeMethod(dialogs, "openJoin")) qmlWarning = true;
        });
        QTimer::singleShot(2650, &app, [&] {
            saveSmokeImage("join-project");
            auto *dialog = engine.rootObjects().first()->findChild<QObject *>("joinProjectDialog");
            if (!dialog || !dialog->property("visible").toBool()) qmlWarning = true;
            else QMetaObject::invokeMethod(dialog, "close");
            controller.createProject("Invite UI test", "Temporary sharing controls");
        });
        QTimer::singleShot(2800, &app, [&] {
            auto *dialogs = engine.rootObjects().first()->findChild<QObject *>("collaborationDialogs");
            if (!dialogs || !QMetaObject::invokeMethod(dialogs, "openInvite")) qmlWarning = true;
        });
        QTimer::singleShot(2950, &app, [&] { saveSmokeImage("invite-people"); });
        QTimer::singleShot(3100, &app, [&] { app.exit(qmlWarning || controller.projectId().isEmpty() ? 1 : 0); });
    }
    if (embeddingTest) {
        auto *inputTimer = new QTimer(&app);
        inputTimer->setInterval(100);
        QObject::connect(inputTimer, &QTimer::timeout, &app, [&, inputTimer] {
            if (controller.surfaceCount() < 1) return;
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            auto *frame = window->findChild<QQuickItem *>("nativeAppFrame");
            if (!frame) return;
            clickItem(window, frame);
            inputTimer->stop();
        });
        inputTimer->start();
        QTimer::singleShot(10000, &app, [&] {
            if (controller.surfaceCount() < 1 || !controller.previewRunning() || !inputForwarded || qmlWarning) {
                qCritical("Native embedding failed (surfaces=%d, input=%d).", controller.surfaceCount(), inputForwarded); app.exit(1);
            } else { qInfo("Separate native client rendered and received canvas input."); app.exit(0); }
        });
    }
    if (parser.isSet("screenshot") && !smoke) QTimer::singleShot(1800, &app, [&] {
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        const bool saved = window && window->grabWindow().save(parser.value("screenshot"));
        app.exit(saved ? 0 : 1);
    });
    return app.exec();
}
