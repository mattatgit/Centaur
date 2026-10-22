#pragma once
#include <QQuickPaintedItem>
#include <QVariantList>

class InkItem : public QQuickPaintedItem {
    Q_OBJECT
    Q_PROPERTY(QString tool READ tool WRITE setTool NOTIFY toolChanged)
    Q_PROPERTY(QVariantList annotations READ annotations WRITE setAnnotations NOTIFY annotationsChanged)
public:
    explicit InkItem(QQuickItem *parent = nullptr);
    QString tool() const { return m_tool; }
    void setTool(const QString &tool);
    QVariantList annotations() const { return m_annotations; }
    void setAnnotations(const QVariantList &annotations);
    void paint(QPainter *painter) override;
signals:
    void toolChanged();
    void annotationsChanged();
    void strokeFinished(const QVariantMap &stroke);
protected:
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void mouseUngrabEvent() override;
private:
    void appendPoint(const QPointF &point);
    void drawStroke(QPainter *painter, const QVariantMap &stroke);
    QString m_tool = "interact";
    QVariantList m_annotations;
    QVariantList m_points;
};
