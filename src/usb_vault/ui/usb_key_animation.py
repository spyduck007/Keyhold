"""A small, dependency-free animated USB key illustration."""

from __future__ import annotations

from math import sin

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class UsbKeyAnimation(QWidget):
    """Draw a softly pulsing USB key while automatic detection is active."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("usbKeyAnimation")
        self.setMinimumSize(176, 154)
        self._phase = 0.0
        self._animation = QPropertyAnimation(self, b"phase", self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(2_100)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)

    def start(self) -> None:
        """Start the waiting animation."""
        self._animation.start()

    def stop(self) -> None:
        """Stop the waiting animation and leave a stable illustration."""
        self._animation.stop()
        self._set_phase(0.0)

    def _get_phase(self) -> float:
        return self._phase

    def _set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = Property(float, _get_phase, _set_phase)

    def paintEvent(self, event: object) -> None:
        """Render a key and expanding detection rings."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)

        pulse = (sin(self._phase * 6.283185307) + 1) / 2
        for base_radius, opacity in ((53, 20), (39, 34), (27, 50)):
            radius = base_radius + pulse * 9
            painter.setPen(QPen(QColor(86, 220, 200, int(opacity * (1 - pulse / 2))), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))

        painter.setPen(QPen(QColor("#7ce6d6"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor("#18384a"))
        painter.drawRoundedRect(QRectF(-30, -12, 60, 48), 9, 9)
        painter.setBrush(QColor("#55d8c5"))
        painter.drawRoundedRect(QRectF(-16, -39, 32, 29), 5, 5)
        painter.setPen(QPen(QColor("#0b2030"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(-8, -33, -8, -20)
        painter.drawLine(8, -33, 8, -20)
        painter.setPen(QPen(QColor("#81ecdc"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(-14, 8, 14, 8)
        painter.drawLine(-14, 20, 5, 20)
