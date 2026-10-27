#include "session.h"
#include <QCoreApplication>
#include <QCommandLineParser>
#include <QCryptographicHash>
#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>
#include <QLocalSocket>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    app.setApplicationName("centaur-host");
    Q_INIT_RESOURCE(starter);
    QCommandLineParser parser; parser.addHelpOption();
    parser.addOption({"data-dir", "Centaur data directory", "path"});
    parser.addOption({"stop", "Stop a background host after closing its Centaur windows"});
    parser.process(app);
    if (parser.value("data-dir").isEmpty()) return 2;
    const auto root = QFileInfo(parser.value("data-dir")).absoluteFilePath();
    if (parser.isSet("stop")) {
        const auto name = "centaur-" + QString::fromLatin1(QCryptographicHash::hash(root.toUtf8(), QCryptographicHash::Sha256).toHex().left(24));
        QLocalSocket socket; socket.connectToServer(name);
        if (!socket.waitForConnected(1000)) return 0;
        socket.write(QJsonDocument(QJsonObject{{"type", "shutdown"}}).toJson(QJsonDocument::Compact) + '\n');
        socket.waitForBytesWritten(1000);
        if (socket.state() != QLocalSocket::UnconnectedState) socket.waitForDisconnected(2000);
        return 0;
    }
    Session session(root); session.start();
    if (!session.isHost()) return 0; // Another launcher won the startup race.
    return app.exec();
}
