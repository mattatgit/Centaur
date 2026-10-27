#pragma once
#include <QQuickPaintedItem>
#include <QSvgRenderer>
#include <QUrl>

// Render original SVG artwork as a colour mask, as Dialogue's CSS masks do.
class SvgIcon : public QQuickPaintedItem {
    Q_OBJECT
    Q_PROPERTY(QUrl source READ source WRITE setSource NOTIFY sourceChanged)
    Q_PROPERTY(QColor color READ color WRITE setColor NOTIFY colorChanged)
public:
    explicit SvgIcon(QQuickItem *parent = nullptr);
    QUrl source() const { return m_source; }
    void setSource(const QUrl &source);
    QColor color() const { return m_color; }
    void setColor(const QColor &color);
    void paint(QPainter *painter) override;
signals:
    void sourceChanged();
    void colorChanged();
private:
    QUrl m_source;
    QColor m_color = QColor("#171717");
    QSvgRenderer m_renderer;
};
