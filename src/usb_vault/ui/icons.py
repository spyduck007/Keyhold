"""Small line icons drawn in Qt so the app has no asset dependency."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


@lru_cache(maxsize=64)
def app_icon(name: str, color: str = "#dce9f8") -> QIcon:
    """Return a crisp, reusable icon from the app's visual language."""
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    pen = QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "plus":
        painter.drawLine(QPointF(10, 4), QPointF(10, 16))
        painter.drawLine(QPointF(4, 10), QPointF(16, 10))
    elif name == "folder":
        path = QPainterPath(QPointF(2.5, 6.5))
        path.lineTo(8, 6.5)
        path.lineTo(10, 8.5)
        path.lineTo(17.5, 8.5)
        path.lineTo(16, 16.5)
        path.lineTo(3.5, 16.5)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "refresh":
        painter.drawArc(QRectF(3, 3, 14, 14), 35 * 16, 285 * 16)
        painter.drawLine(QPointF(15.3, 3.8), QPointF(16.8, 7.2))
        painter.drawLine(QPointF(15.3, 3.8), QPointF(11.8, 4.4))
    elif name == "edit":
        painter.drawLine(QPointF(4, 16), QPointF(15, 5))
        painter.drawLine(QPointF(12.8, 4.8), QPointF(15.2, 7.2))
        painter.drawLine(QPointF(4, 16), QPointF(7.5, 15.2))
    elif name == "trash":
        painter.drawRoundedRect(QRectF(5, 6.5, 10, 10.5), 1, 1)
        painter.drawLine(QPointF(3.7, 5), QPointF(16.3, 5))
        painter.drawLine(QPointF(8, 2.8), QPointF(12, 2.8))
        painter.drawLine(QPointF(8, 9), QPointF(8, 14.5))
        painter.drawLine(QPointF(12, 9), QPointF(12, 14.5))
    elif name == "lock":
        painter.drawRoundedRect(QRectF(4, 8.5, 12, 9), 2, 2)
        painter.drawArc(QRectF(6.5, 2.5, 7, 10), 0, 180 * 16)
    elif name == "arrow_right":
        painter.drawLine(QPointF(3, 10), QPointF(16, 10))
        painter.drawLine(QPointF(11.5, 5.5), QPointF(16, 10))
        painter.drawLine(QPointF(11.5, 14.5), QPointF(16, 10))
    elif name == "back":
        painter.drawLine(QPointF(17, 10), QPointF(4, 10))
        painter.drawLine(QPointF(8.5, 5.5), QPointF(4, 10))
        painter.drawLine(QPointF(8.5, 14.5), QPointF(4, 10))
    elif name == "download":
        painter.drawLine(QPointF(10, 3), QPointF(10, 13))
        painter.drawLine(QPointF(6, 9), QPointF(10, 13))
        painter.drawLine(QPointF(14, 9), QPointF(10, 13))
        painter.drawLine(QPointF(4, 17), QPointF(16, 17))
    elif name == "key":
        painter.drawEllipse(QRectF(2.5, 4.5, 7, 7))
        painter.drawLine(QPointF(8.5, 10.5), QPointF(17, 16))
        painter.drawLine(QPointF(13, 13.2), QPointF(15, 11.2))
        painter.drawLine(QPointF(15, 14.7), QPointF(17, 12.7))
    elif name == "shield":
        painter.drawPolygon(
            QPolygonF(
                (
                    QPointF(10, 2.5),
                    QPointF(16, 5),
                    QPointF(15, 12.5),
                    QPointF(10, 17.5),
                    QPointF(5, 12.5),
                    QPointF(4, 5),
                )
            )
        )
    elif name == "copy":
        painter.drawRoundedRect(QRectF(6.5, 6.5, 10, 10), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(3, 3, 10, 10), 1.5, 1.5)
    elif name == "file":
        path = QPainterPath(QPointF(5, 2.5))
        path.lineTo(12, 2.5)
        path.lineTo(16, 6.5)
        path.lineTo(16, 17.5)
        path.lineTo(5, 17.5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(12, 2.5), QPointF(12, 6.5))
        painter.drawLine(QPointF(12, 6.5), QPointF(16, 6.5))
    elif name == "more":
        painter.setBrush(QColor(color))
        for x in (5.5, 10, 14.5):
            painter.drawEllipse(QPointF(x, 10), 1.1, 1.1)
    elif name == "chevron_right":
        painter.drawLine(QPointF(7, 4.5), QPointF(12.5, 10))
        painter.drawLine(QPointF(12.5, 10), QPointF(7, 15.5))
    elif name == "check":
        painter.drawLine(QPointF(3.5, 10), QPointF(8, 14.5))
        painter.drawLine(QPointF(8, 14.5), QPointF(16.5, 5.5))
    elif name == "search":
        painter.drawEllipse(QRectF(3, 3, 10.5, 10.5))
        painter.drawLine(QPointF(11.2, 11.2), QPointF(17, 17))
    elif name == "image":
        painter.drawRoundedRect(QRectF(2.5, 3.5, 15, 13), 2, 2)
        painter.drawEllipse(QRectF(5, 6, 2.5, 2.5))
        painter.drawLine(QPointF(4.5, 14), QPointF(9, 10))
        painter.drawLine(QPointF(9, 10), QPointF(12, 13))
        painter.drawLine(QPointF(12, 13), QPointF(15, 9.5))
    elif name == "pdf":
        path = QPainterPath(QPointF(5, 2.5))
        path.lineTo(12, 2.5)
        path.lineTo(16, 6.5)
        path.lineTo(16, 17.5)
        path.lineTo(5, 17.5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(QPen(QColor(color), 1.35))
        painter.drawText(QRectF(5.2, 8, 10.5, 7), Qt.AlignmentFlag.AlignCenter, "PDF")
    elif name == "text":
        painter.drawRoundedRect(QRectF(4, 2.5, 12, 15), 1.5, 1.5)
        painter.drawLine(QPointF(7, 7), QPointF(13, 7))
        painter.drawLine(QPointF(7, 10.5), QPointF(13, 10.5))
        painter.drawLine(QPointF(7, 14), QPointF(11, 14))
    else:
        raise ValueError(f"unknown icon: {name}")

    painter.end()
    return QIcon(pixmap)
