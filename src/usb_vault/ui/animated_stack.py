"""A QStackedWidget with restrained horizontal page transitions."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation
from PySide6.QtWidgets import QStackedWidget, QWidget


class AnimatedStackedWidget(QStackedWidget):
    """Slide between application pages while preserving normal stack semantics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animation_group: QParallelAnimationGroup | None = None
        self._outgoing_widget: QWidget | None = None
        self._incoming_widget: QWidget | None = None

    def setCurrentWidget(self, widget: QWidget) -> None:
        """Select a page and animate it when the stack is visible."""
        current = self.currentWidget()
        if current is widget:
            return

        if current is None or not self.isVisible() or self.width() <= 1:
            super().setCurrentWidget(widget)
            return

        self._finish_active_transition()

        outgoing_index = self.indexOf(current)
        incoming_index = self.indexOf(widget)
        direction = 1 if incoming_index >= outgoing_index else -1
        distance = self.width()

        super().setCurrentWidget(widget)
        widget.setGeometry(self.rect())
        widget.move(direction * distance, 0)
        widget.show()
        current.setGeometry(self.rect())
        current.move(0, 0)
        current.show()
        widget.raise_()

        outgoing_animation = QPropertyAnimation(current, b"pos", self)
        outgoing_animation.setDuration(320)
        outgoing_animation.setStartValue(QPoint(0, 0))
        outgoing_animation.setEndValue(QPoint(-direction * distance, 0))
        outgoing_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        incoming_animation = QPropertyAnimation(widget, b"pos", self)
        incoming_animation.setDuration(320)
        incoming_animation.setStartValue(QPoint(direction * distance, 0))
        incoming_animation.setEndValue(QPoint(0, 0))
        incoming_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(outgoing_animation)
        group.addAnimation(incoming_animation)
        group.finished.connect(self._finish_active_transition)

        self._animation_group = group
        self._outgoing_widget = current
        self._incoming_widget = widget
        group.start()

    def _finish_active_transition(self) -> None:
        group = self._animation_group
        self._animation_group = None
        if group is not None:
            group.stop()

        if self._outgoing_widget is not None:
            self._outgoing_widget.hide()
            self._outgoing_widget.move(0, 0)

        if self._incoming_widget is not None:
            self._incoming_widget.move(0, 0)
            self._incoming_widget.show()

        self._outgoing_widget = None
        self._incoming_widget = None
