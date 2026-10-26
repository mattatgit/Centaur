#include "typography.h"
#include <QFontDatabase>
#include <QGuiApplication>
#include <QDebug>

bool initializeTypography() {
    Q_INIT_RESOURCE(fonts);
    for (const auto *file : {":/fonts/Inter-Regular.ttf", ":/fonts/Inter-SemiBold.ttf", ":/fonts/Inter-Bold.ttf"}) {
        const auto id = QFontDatabase::addApplicationFont(QString::fromLatin1(file));
        if (id < 0 || !QFontDatabase::applicationFontFamilies(id).contains("Inter")) {
            qCritical() << "Could not load the bundled Inter font:" << file;
            return false;
        }
    }
    auto font = QGuiApplication::font();
    font.setFamily("Inter");
    QGuiApplication::setFont(font);
    return true;
}
