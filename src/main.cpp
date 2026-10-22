#include "controller.h"
#include "inkitem.h"
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

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    QCoreApplication::setApplicationName("Centaur");
    QCoreApplication::setOrganizationName("Centaur");
    QCoreApplication::setApplicationVersion("0.1.0");
    QQuickStyle::setStyle("Basic");
    Q_INIT_RESOURCE(starter);
    QCommandLineParser parser;
    parser.setApplicationDescription("A native workshop for making apps together.");
    parser.addHelpOption(); parser.addVersionOption();
    parser.addOption({"data-dir", "Project and shared session directory.", "path"});
    parser.addOption({"smoke-test", "Load the native UI and exit (temporary data only)."});
    parser.addOption({"embedding-smoke-test", "Verify that a separate native app maps inside the canvas."});
    parser.addOption({"screenshot", "Save a native UI screenshot and exit.", "path"});
    parser.addOption({"demo", "Create and open a starter project if no projects exist."});
    parser.process(app);
    const bool smoke = parser.isSet("smoke-test");
    const bool embeddingTest = parser.isSet("embedding-smoke-test");
    QTemporaryDir temporary;
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
    QQmlApplicationEngine engine;
    QObject::connect(&app, &QCoreApplication::aboutToQuit, &app, [&controller] { controller.stopPreview(); });
    engine.rootContext()->setContextProperty("Backend", &controller);
    bool qmlWarning = false;
    QObject::connect(&engine, &QQmlEngine::warnings, &app, [&qmlWarning] { qmlWarning = true; });
    engine.load(QUrl("qrc:/qml/Main.qml"));
    if (engine.rootObjects().isEmpty()) return 1;
    if (embeddingTest) {
        Workspace workspace(root);
        QString error;
        const auto id = workspace.createProject("Embedding test", "Temporary native client probe", &error);
        QFile probe(":/tests/fixtures/EmbeddedProbe.qml");
        if (id.isEmpty() || !probe.open(QIODevice::ReadOnly)
            || !Workspace::writeFile(workspace.projectPath(id) + "/App.qml", probe.readAll())) return 1;
    }
    controller.start();
    if (embeddingTest || parser.isSet("demo")) {
        if (controller.projects().isEmpty()) controller.createProject("Family board", "A little space for everyday things, made together.");
        else controller.openProject(controller.projects().first().toMap()["id"].toString());
    }
    if (smoke) {
        // Exercise both main views and all their QML components.
        QTimer::singleShot(100, &app, [&] {
            controller.createProject("UI test", "Temporary smoke-test project");
            controller.setAuthor("Matt"); controller.sendMessage("Let's make something simple.");
            controller.setAuthor("Saori"); controller.sendMessage("And easy for everyone to use.");
            controller.addAnnotation({{"tool", "draw"}, {"points", QVariantList{
                QVariantMap{{"x", 0.1}, {"y", 0.2}}, QVariantMap{{"x", 0.2}, {"y", 0.3}}}}});
        });
        QTimer::singleShot(1200, &app, [&] { app.exit(qmlWarning || controller.projectId().isEmpty() ? 1 : 0); });
    }
    if (embeddingTest) {
        auto *inputTimer = new QTimer(&app);
        inputTimer->setInterval(100);
        QObject::connect(inputTimer, &QTimer::timeout, &app, [&, inputTimer] {
            if (controller.surfaceCount() < 1) return;
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            auto *frame = window->findChild<QQuickItem *>("nativeAppFrame");
            if (!frame) return;
            const auto position = frame->mapToScene(QPointF(frame->width() / 2, frame->height() / 2));
            const QPointF global = window->mapToGlobal(position.toPoint());
            QMouseEvent press(QEvent::MouseButtonPress, position, global, Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
            QMouseEvent release(QEvent::MouseButtonRelease, position, global, Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
            QCoreApplication::sendEvent(window, &press);
            QCoreApplication::sendEvent(window, &release);
            inputTimer->stop();
        });
        inputTimer->start();
        QTimer::singleShot(10000, &app, [&] {
            if (controller.surfaceCount() < 1 || !controller.previewRunning() || !inputForwarded || qmlWarning) {
                qCritical("Native embedding failed (surfaces=%d, input=%d).", controller.surfaceCount(), inputForwarded); app.exit(1);
            } else { qInfo("Separate native client rendered and received canvas input."); app.exit(0); }
        });
    }
    if (parser.isSet("screenshot")) QTimer::singleShot(1800, &app, [&] {
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        const bool saved = window && window->grabWindow().save(parser.value("screenshot"));
        app.exit(saved ? 0 : 1);
    });
    return app.exec();
}
