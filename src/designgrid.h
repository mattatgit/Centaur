#pragma once
#include <QQuickPaintedItem>

class DesignGrid : public QQuickPaintedItem {
    Q_OBJECT
    Q_PROPERTY(int step READ step WRITE setStep NOTIFY changed)
    Q_PROPERTY(QColor color READ color WRITE setColor NOTIFY changed)
    Q_PROPERTY(QPointF origin READ origin WRITE setOrigin NOTIFY changed)
public:
    explicit DesignGrid(QQuickItem *parent = nullptr);
    int step() const { return m_step; }
    void setStep(int step);
    QColor color() const { return m_color; }
    void setColor(const QColor &color);
    QPointF origin() const { return m_origin; }
    void setOrigin(const QPointF &origin);
    void paint(QPainter *painter) override;
signals:
    void changed();
private:
    int m_step = 8;
    QColor m_color = QColor("#BAE6FF");
    QPointF m_origin;
};
