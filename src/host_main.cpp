#include "session.h"
#include <QCoreApplication>
#include <QCommandLineParser>
#include <QCryptographicHash>
#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>
#include <QLocalSocket>
#include <QElapsedTimer>
#include <QThread>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    app.setApplicationName("centaur-host");
    Q_INIT_RESOURCE(starter);
    QCommandLineParser parser; parser.addHelpOption();
    parser.addOption({"data-dir", "Centaur data directory", "path"});
    parser.addOption({"stop", "Stop a background host after closing its Centaur windows"});
    parser.addOption({"stop-if-idle", "Stop only when requests, checks and other local windows are idle"});
    parser.addOption({"finish-update", "Release a staged update's startup gate", "token"});
    parser.addOption({"update-token", "Staged update token", "token"});
    parser.process(app);
    if (parser.value("data-dir").isEmpty()) return 2;
    const auto root = QFileInfo(parser.value("data-dir")).absoluteFilePath();
    if (parser.isSet("stop") || parser.isSet("stop-if-idle") || parser.isSet("finish-update")) {
        const auto name = "centaur-" + QString::fromLatin1(QCryptographicHash::hash(root.toUtf8(), QCryptographicHash::Sha256).toHex().left(24));
        QLocalSocket socket; socket.connectToServer(name);
        if (!socket.waitForConnected(1000)) {
            if (parser.isSet("finish-update")) return 1;
            if (parser.isSet("stop-if-idle")) {
                QLockFile lock(root + "/session.lock");
                if (!lock.tryLock(0)) { qWarning("Could not confirm that the existing host is idle."); return 3; }
                lock.unlock();
            }
            return 0;
        }
        const bool safe = parser.isSet("stop-if-idle") || parser.isSet("finish-update");
        const auto type = parser.isSet("finish-update") ? "finishUpdate" : safe ? "shutdownIfIdle" : "shutdown";
        const auto token = parser.isSet("finish-update") ? parser.value("finish-update") : parser.value("update-token");
        socket.write(QJsonDocument(QJsonObject{{"type", type}, {"token", token}}).toJson(QJsonDocument::Compact) + '\n');
        socket.waitForBytesWritten(1000);
        if (safe) {
            QElapsedTimer timer; timer.start(); QByteArray buffer; bool accepted = false;
            while (timer.elapsed() < 4000 && !accepted) {
                buffer += socket.readAll();
                while (buffer.contains('\n')) {
                    const int end = buffer.indexOf('\n');
                    const auto response = QJsonDocument::fromJson(buffer.left(end)).object(); buffer.remove(0,end+1);
                    if (response["type"] == "error") { qWarning().noquote() << response["message"].toString(); return 3; }
                    accepted = response["type"] == (parser.isSet("finish-update") ? "updateResumed" : "updateStopping");
                    if (accepted) break;
                }
                if (!accepted) socket.waitForReadyRead(200);
            }
            if (!accepted) return 1;
            if (parser.isSet("finish-update")) return 0;
        }
        if (socket.state() != QLocalSocket::UnconnectedState) socket.waitForDisconnected(2000);
        if (safe) {
            QLockFile lock(root + "/session.lock"); QElapsedTimer timer; timer.start();
            while (!lock.tryLock(0)) { if (timer.elapsed() > 5000) return 1; QThread::msleep(50); }
            lock.unlock();
        }
        return 0;
    }
    Session session(root); session.start();
    if (!session.isHost()) return 0; // Another launcher won the startup race.
    return app.exec();
}
