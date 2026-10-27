#include "svgicon.h"
#include <QPainter>

SvgIcon::SvgIcon(QQuickItem *parent) : QQuickPaintedItem(parent) {
    setAntialiasing(true);
    setAcceptedMouseButtons(Qt::NoButton);
    m_renderer.setAspectRatioMode(Qt::KeepAspectRatio);
}
void SvgIcon::setSource(const QUrl &source) {
    if (m_source == source) return;
    m_source = source;
    const auto path = source.scheme() == "qrc" ? ":" + source.path() : source.toLocalFile();
    if (!source.isEmpty() && !m_renderer.load(path)) qWarning() << "Could not load SVG icon:" << source;
    update(); emit sourceChanged();
}
void SvgIcon::setColor(const QColor &color) {
    if (m_color == color) return;
    m_color = color; update(); emit colorChanged();
}
void SvgIcon::paint(QPainter *painter) {
    if (m_source.isEmpty() || !m_renderer.isValid()) return;
    painter->save();
    m_renderer.render(painter, boundingRect());
    painter->setCompositionMode(QPainter::CompositionMode_SourceIn);
    painter->fillRect(boundingRect(), m_color);
    painter->restore();
}
