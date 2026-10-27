#include "designgrid.h"
#include <QPainter>
#include <cmath>

DesignGrid::DesignGrid(QQuickItem *parent) : QQuickPaintedItem(parent) { setAcceptedMouseButtons(Qt::NoButton); }
void DesignGrid::setStep(int step) {
    step = qBound(2, step, 64);
    if (m_step == step) return;
    m_step = step; update(); emit changed();
}
void DesignGrid::setColor(const QColor &color) {
    if (!color.isValid() || m_color == color) return;
    m_color = color; update(); emit changed();
}
void DesignGrid::setOrigin(const QPointF &origin) {
    if (m_origin == origin) return;
    m_origin = origin; update(); emit changed();
}
void DesignGrid::paint(QPainter *painter) {
    painter->setPen(QPen(m_color, 1));
    const auto offset = [this](qreal value) { return std::fmod(std::fmod(value, m_step) + m_step, m_step); };
    for (qreal x = offset(m_origin.x()); x < width(); x += m_step) painter->drawLine(QPointF(x, 0), QPointF(x, height()));
    for (qreal y = offset(m_origin.y()); y < height(); y += m_step) painter->drawLine(QPointF(0, y), QPointF(width(), y));
}
