#pragma once
#include <QObject>

class TypefaceSelector : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    Q_INVOKABLE QString familyForSize(qreal points, int pixels) const;
};

// Call once after constructing QGuiApplication, before creating QML engines.
// Each native process registers its own bundled fonts.
bool initializeTypography();
