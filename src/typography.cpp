#include "typography.h"
#include <QFontDatabase>
#include <QGuiApplication>
#include <QDebug>
#include <QFontInfo>
#include <qqml.h>

QString TypefaceSelector::familyForSize(qreal points, int pixels) const {
    if (points <= 0 && pixels > 0) {
        QFont font("Inter"); font.setPixelSize(pixels);
        points = QFontInfo(font).pointSizeF();
    }
    return points > 12.0 + 0.001 ? QStringLiteral("Inter Tight") : QStringLiteral("Inter");
}

bool initializeTypography() {
    Q_INIT_RESOURCE(fonts);
    Q_INIT_RESOURCE(tight_fonts);
    for (const auto *file : {":/fonts/Inter-Regular.ttf", ":/fonts/Inter-SemiBold.ttf", ":/fonts/Inter-Bold.ttf"}) {
        const auto id = QFontDatabase::addApplicationFont(QString::fromLatin1(file));
        if (id < 0 || !QFontDatabase::applicationFontFamilies(id).contains("Inter")) {
            qCritical() << "Could not load the bundled Inter font:" << file;
            return false;
        }
    }
    const auto tight = QFontDatabase::addApplicationFont(":/fonts/InterTight-Variable.ttf");
    if (tight < 0 || !QFontDatabase::applicationFontFamilies(tight).contains("Inter Tight")) {
        qCritical() << "Could not load the bundled Inter Tight font";
        return false;
    }
    qmlRegisterType<TypefaceSelector>("Centaur.Typography", 1, 0, "TypefaceSelector");
    auto font = QGuiApplication::font();
    font.setFamily("Inter");
    QGuiApplication::setFont(font);
    return true;
}
