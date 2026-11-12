// Temporary non-visual bridge: retain the existing coordinator/network/OMP
// implementation while the frontend and generated apps move to GTK4.
#include "controller.h"
#include <QCoreApplication>
#include <QCommandLineParser>
#include <QSocketNotifier>
#include <QJsonDocument>
#include <QJsonArray>
#include <QDir>
#include <unistd.h>

static void output(const QJsonObject &value) {
    const auto bytes = QJsonDocument(value).toJson(QJsonDocument::Compact) + '\n';
    const char *data = bytes.constData();
    qint64 remaining = bytes.size();
    while (remaining > 0) { const auto n = ::write(1, data, remaining); if (n <= 0) return; data += n; remaining -= n; }
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    qputenv("CENTAUR_GTK_CLIENT", "1");
    app.setApplicationName("centaur-gtk4-bridge");
    Q_INIT_RESOURCE(starter);
    QCommandLineParser parser; parser.addHelpOption();
    parser.addOption({"data-dir", "Project data directory", "path"}); parser.process(app);
    if (parser.value("data-dir").isEmpty()) return 2;
    Controller controller(QDir(parser.value("data-dir")).absolutePath());
    auto snapshot = [&] {
        const auto state = QJsonObject::fromVariantMap(controller.project());
        const auto path = controller.dataRoot() + (controller.remoteProject() ? "/shared/" : "/projects/") + controller.projectId();
        output({{"type", "snapshot"}, {"projects", QJsonArray::fromVariantList(controller.projects())},
            {"project", state}, {"author", controller.author()}, {"remote", controller.remoteProject()},
            {"connected", controller.canContribute()}, {"status", controller.connectionStatus()},
            {"busy", controller.agentBusy()}, {"agentAvailable", controller.agentAvailable()},
            {"updateBlocked", controller.updateBlocked()}, {"updateHeld", controller.updateHeld()},
            {"snapshotReady", controller.snapshotReady()},
            {"agentModel", controller.agentModel()}, {"agentExecutable", controller.agentExecutable()},
            {"invitation", controller.invitationCode()}, {"inviting", controller.inviting()}, {"localAddress", controller.localAddress()},
            {"joinStatus", controller.joinStatus()}, {"joining", controller.joining()},
            {"sourcePath", state.isEmpty() ? QString() : path + "/" + Workspace::sourceName(state)},
            {"grid", QJsonObject{{"enabled", controller.gridEnabled()}, {"size", controller.gridSize()}, {"opacity", controller.gridOpacity()}, {"color", controller.gridColor().name()}}}});
    };
    QObject::connect(&controller, &Controller::changed, &app, snapshot);
    QObject::connect(&controller, &Controller::preferencesChanged, &app, snapshot);
    QObject::connect(&controller, &Controller::error, &app, [](const QString &error) { output({{"type", "error"}, {"message", error}}); });
    QByteArray buffer;
    QSocketNotifier input(0, QSocketNotifier::Read);
    QObject::connect(&input, &QSocketNotifier::activated, &app, [&] {
        char bytes[65536]; const auto count = ::read(0, bytes, sizeof bytes);
        if (count <= 0) { app.quit(); return; }
        buffer.append(bytes, count);
        if (buffer.size() > 1024*1024) { app.quit(); return; }
        while (buffer.contains('\n')) {
            const auto end = buffer.indexOf('\n');
            const auto command = QJsonDocument::fromJson(buffer.left(end)).object(); buffer.remove(0, end+1);
            const auto type = command["type"].toString();
            const auto id = command["projectId"].toString();
            if (type == "create") controller.createGtkProject(command["name"].toString(), command["description"].toString());
            else if (type == "importProject") controller.importGtkProject(command);
            else if (type == "retryImport" || type == "runImport") controller.importAction(type,command["source"].toObject());
            else if (type == "open") controller.openProject(id);
            else if (type == "close") controller.closeProject();
            else if (type == "author") controller.setAuthor(command["name"].toString());
            else if (type == "message") { if (controller.sendMessage(command["text"].toString(), command["image"].toString(), command["imageRevision"].toInt(), command["comment"].toObject())) output({{"type", "sent"}, {"text", command["text"]}}); }
            else if (type == "rename") controller.renameProject(id, command["name"].toString());
            else if (type == "delete") controller.deleteProject(id);
            else if (type == "archive") controller.archiveProject(id);
            else if (type == "invite") controller.invitePeople(command["address"].toString("iroh"));
            else if (type == "stopSharing") controller.stopSharing();
            else if (type == "join") controller.joinProject(command["code"].toString(), command["name"].toString());
            else if (type == "cancelJoin") controller.cancelJoin();
            else if (type == "leave") controller.leaveProject(id);
            else if (type == "accept") controller.acceptProposal();
            else if (type == "cancel") controller.cancelAgent();
            else if (type == "agentName") controller.renameAgent(command["name"].toString());
            else if (type == "annotation") controller.addAnnotation(command["annotation"].toObject().toVariantMap());
            else if (type == "undo") controller.undoAnnotation();
            else if (type == "grid") { controller.setGridEnabled(command["enabled"].toBool()); controller.setGridSize(command["size"].toInt(8)); controller.setGridOpacity(command["opacity"].toInt(50)); if (command.contains("color")) controller.setGridColor(QColor(command["color"].toString())); }
            else if (type == "snapshot") snapshot();
            else output({{"type", "error"}, {"message", "Unknown frontend command."}});
        }
    });
    controller.start(true);
    return app.exec();
}
