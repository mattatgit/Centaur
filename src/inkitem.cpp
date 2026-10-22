#include "inkitem.h"
#include <QPainter>
#include <QPainterPath>
#include <QMouseEvent>
#include <QCursor>
#include <QtMath>

InkItem::InkItem(QQuickItem *parent) : QQuickPaintedItem(parent) {
    setAntialiasing(true);
    setAcceptedMouseButtons(Qt::NoButton);
}
void InkItem::setTool(const QString &tool) {
    if (m_tool == tool) return;
    m_tool = tool; m_points.clear();
    setAcceptedMouseButtons(tool == "interact" ? Qt::NoButton : Qt::LeftButton);
    if (tool == "interact") unsetCursor();
    else setCursor(Qt::CrossCursor);
    update(); emit toolChanged();
}
void InkItem::setAnnotations(const QVariantList &annotations) { m_annotations = annotations; update(); emit annotationsChanged(); }
void InkItem::appendPoint(const QPointF &point) {
    if (width() <= 0 || height() <= 0 || m_points.size() >= 4096) return;
    const auto normalized = QPointF(qBound(0.0, point.x() / width(), 1.0), qBound(0.0, point.y() / height(), 1.0));
    if (!m_points.isEmpty()) {
        const auto last = m_points.last().toMap();
        const QPointF previous(last["x"].toDouble() * width(), last["y"].toDouble() * height());
        if (QLineF(previous, point).length() < 2) return;
    }
    const QVariantMap next{{"x", normalized.x()}, {"y", normalized.y()}};
    if (m_tool == "comment" && m_points.size() == 2) m_points[1] = next;
    else m_points.append(next);
    update();
}
void InkItem::mousePressEvent(QMouseEvent *event) { m_points.clear(); appendPoint(event->position()); event->accept(); }
void InkItem::mouseMoveEvent(QMouseEvent *event) { appendPoint(event->position()); event->accept(); }
void InkItem::mouseReleaseEvent(QMouseEvent *event) {
    appendPoint(event->position());
    if (!m_points.isEmpty()) emit strokeFinished({{"tool", m_tool}, {"points", m_points}});
    m_points.clear(); update(); event->accept();
}
void InkItem::mouseUngrabEvent() { m_points.clear(); update(); }
void InkItem::drawStroke(QPainter *painter, const QVariantMap &stroke) {
    const auto points = stroke["points"].toList();
    if (points.isEmpty()) return;
    const bool arrow = stroke["tool"].toString() == "comment";
    const QColor color(arrow ? "#ff6060" : "#426bc9");
    painter->setPen(QPen(color, 2.5, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    auto position = [this](const QVariant &v) { auto p = v.toMap(); return QPointF(p["x"].toDouble() * width(), p["y"].toDouble() * height()); };
    QPainterPath path(position(points.first()));
    if (points.size() == 1) painter->drawPoint(position(points.first()));
    for (int i = 1; i < points.size(); ++i) path.lineTo(position(points[i]));
    painter->drawPath(path);
    if (arrow && points.size() > 1) {
        const auto end = position(points.last());
        const auto start = position(points.first());
        if (QLineF(start, end).length() < 3) return;
        const double angle = std::atan2(end.y() - start.y(), end.x() - start.x());
        for (double delta : {-0.45, 0.45}) painter->drawLine(end,
            end - QPointF(std::cos(angle + delta) * 12, std::sin(angle + delta) * 12));
        painter->setBrush(color); painter->drawEllipse(start, 3, 3);
    }
}
void InkItem::paint(QPainter *painter) {
    painter->setRenderHint(QPainter::Antialiasing);
    for (const auto &annotation : m_annotations) drawStroke(painter, annotation.toMap());
    if (!m_points.isEmpty()) drawStroke(painter, {{"tool", m_tool}, {"points", m_points}});
}
