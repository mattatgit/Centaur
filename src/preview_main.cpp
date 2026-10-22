#include <QGuiApplication>
#include <QQuickView>
#include <QQuickItem>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickStyle>
#include <QTimer>
#include <QFileInfo>

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    QCoreApplication::setApplicationName("Centaur Native Preview");
    QQuickStyle::setStyle("Basic");
    const auto args = app.arguments();
    const bool check = args.contains("--check");
    const QString path = args.isEmpty() ? QString() : args.last();
    if (!QFileInfo(path).isFile()) { qCritical("Give centaur-preview an App.qml file."); return 1; }
    if (check) {
        QQmlEngine engine;
        QQmlComponent component(&engine, QUrl::fromLocalFile(QFileInfo(path).absoluteFilePath()));
        QScopedPointer<QObject> root(component.create());
        if (!root || !qobject_cast<QQuickItem *>(root.data())) {
            qCritical().noquote() << component.errorString();
            qCritical("App.qml must have an Item or Rectangle as its root.");
            return 1;
        }
        return 0;
    }
    QQuickView view;
    view.setTitle("Centaur app");
    view.setResizeMode(QQuickView::SizeRootObjectToView);
    view.resize(520, 640);
    view.setSource(QUrl::fromLocalFile(QFileInfo(path).absoluteFilePath()));
    if (view.status() == QQuickView::Error) return 1;
    view.show();
    qInfo("CENTAUR_READY");
    return app.exec();
}
