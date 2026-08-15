"""Reusable visual primitives for the Keyhold desktop interface."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.branding import APP_NAME, APP_TAGLINE

CONTENT_MAX_WIDTH = 1_180
FORM_MAX_WIDTH = 700
AUTH_PANEL_MAX_WIDTH = 620

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_6 = 24
SPACE_8 = 32
SPACE_12 = 48


class ResponsivePage(QWidget):
    """A top-aligned page with responsive gutters and a real content max-width."""

    def __init__(
        self,
        object_name: str,
        *,
        max_width: int = CONTENT_MAX_WIDTH,
        center_vertically: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)

        self.content = QWidget()
        self.content.setObjectName("pageContent")
        self.content.setMaximumWidth(max_width)
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(SPACE_4)

        self._outer_layout = QHBoxLayout(self)
        outer_alignment = Qt.AlignmentFlag.AlignHCenter
        if not center_vertically:
            outer_alignment |= Qt.AlignmentFlag.AlignTop
        self._outer_layout.setAlignment(outer_alignment)
        self._outer_layout.addWidget(self.content)
        self._update_gutters()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_gutters()

    def _update_gutters(self) -> None:
        width = self.width()

        if width < 900:
            horizontal = SPACE_6
            vertical = SPACE_6
        elif width < 1_280:
            horizontal = SPACE_8
            vertical = SPACE_8
        else:
            horizontal = SPACE_12
            vertical = SPACE_8

        self._outer_layout.setContentsMargins(
            horizontal,
            vertical,
            horizontal,
            vertical,
        )


class AppSidebar(QFrame):
    """Persistent navigation for the app's existing workflows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("appSidebar")
        self.setFixedWidth(224)
        self._buttons: dict[str, QPushButton] = {}
        self._requested_enabled: dict[str, bool] = {}
        self._busy = False

        self.brand_icon = QLabel()
        self.brand_icon.setObjectName("sidebarBrandIcon")
        self.brand_icon.setFixedSize(32, 32)

        brand_name = QLabel(APP_NAME)
        brand_name.setObjectName("sidebarBrandName")
        brand_detail = QLabel(APP_TAGLINE)
        brand_detail.setObjectName("sidebarBrandDetail")
        brand_copy = QVBoxLayout()
        brand_copy.setContentsMargins(0, 0, 0, 0)
        brand_copy.setSpacing(0)
        brand_copy.addWidget(brand_name)
        brand_copy.addWidget(brand_detail)
        brand = QHBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(SPACE_3)
        brand.addWidget(self.brand_icon)
        brand.addLayout(brand_copy, 1)

        self._groups: dict[str, QVBoxLayout] = {}
        navigation = QVBoxLayout()
        navigation.setContentsMargins(0, 0, 0, 0)
        navigation.setSpacing(SPACE_6)
        for key, label in (
            ("vaults", "VAULTS"),
            ("access", "ACCESS"),
            ("session", "SESSION"),
        ):
            group_label = QLabel(label)
            group_label.setObjectName("sidebarSectionLabel")
            group_layout = QVBoxLayout()
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(SPACE_1)
            group_layout.addWidget(group_label)
            self._groups[key] = group_layout
            navigation.addLayout(group_layout)

        self.session_name = QLabel("No vault open")
        self.session_name.setObjectName("sidebarSessionName")
        self.session_state = QLabel("Locked")
        self.session_state.setObjectName("sidebarSessionState")

        session_card = QFrame()
        session_card.setObjectName("sidebarSessionCard")
        session_layout = QVBoxLayout(session_card)
        session_layout.setContentsMargins(SPACE_3, SPACE_3, SPACE_3, SPACE_3)
        session_layout.setSpacing(SPACE_1)
        session_layout.addWidget(self.session_name)
        session_layout.addWidget(self.session_state)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_6, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_8)
        layout.addLayout(brand)
        layout.addLayout(navigation)
        layout.addStretch()
        layout.addWidget(session_card)

    def set_brand_icon(self, icon: QIcon) -> None:
        self.brand_icon.setPixmap(icon.pixmap(26, 26))

    def add_item(
        self,
        key: str,
        label: str,
        icon: QIcon,
        callback: Callable[[], None],
        *,
        group: str,
        enabled: bool = True,
    ) -> QPushButton:
        if key in self._buttons:
            raise ValueError(f"sidebar item already exists: {key}")
        if group not in self._groups:
            raise ValueError(f"unknown sidebar group: {group}")

        button = QPushButton(label)
        button.setObjectName("sidebarNavButton")
        button.setProperty("active", False)
        button.setIcon(icon)
        button.setCheckable(False)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        button.setEnabled(enabled)
        self._groups[group].addWidget(button)
        self._buttons[key] = button
        self._requested_enabled[key] = enabled
        return button

    def set_active(self, key: str | None) -> None:
        for item_key, button in self._buttons.items():
            button.setProperty("active", item_key == key)
            button.style().unpolish(button)
            button.style().polish(button)

    def item_button(self, key: str) -> QPushButton | None:
        return self._buttons.get(key)

    def set_item_enabled(self, key: str, enabled: bool) -> None:
        button = self._buttons.get(key)
        if button is None:
            return
        self._requested_enabled[key] = enabled
        button.setEnabled(enabled and (not self._busy or key in {"lock", "quit"}))

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        for key, button in self._buttons.items():
            requested = self._requested_enabled.get(key, True)
            button.setEnabled(requested and (not busy or key in {"lock", "quit"}))

    def set_session(self, name: str, state: str) -> None:
        self.session_name.setText(name)
        self.session_name.setToolTip(name)
        self.session_state.setText(state)


def form_label(text: str) -> QLabel:
    """A QFormLayout row label styled consistently with the rest of the app."""
    label = QLabel(text)
    label.setObjectName("formLabel")
    return label


class PageHeader(QWidget):
    """Consistent eyebrow, title, description, context, and action header."""

    def __init__(
        self,
        eyebrow: str,
        title: str,
        description: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")

        self.eyebrow_label = QLabel(eyebrow)
        self.eyebrow_label.setObjectName("pageHeaderEyebrow")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageHeaderTitle")
        self.title_label.setWordWrap(True)

        self.description_label = QLabel(description)
        self.description_label.setObjectName("pageHeaderDescription")
        self.description_label.setWordWrap(True)

        self.context_label = ElidedLabel()
        self.context_label.setObjectName("pageHeaderContext")
        self.context_label.hide()

        self.action_area = QWidget()
        self.action_area.setObjectName("pageHeaderActions")
        self.action_layout = QHBoxLayout(self.action_area)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(SPACE_2)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(SPACE_1)
        title_column.addWidget(self.title_label)
        title_column.addWidget(self.description_label)
        title_column.addWidget(self.context_label)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(SPACE_6)
        title_row.addLayout(title_column, 1)
        title_row.addWidget(self.action_area, 0, Qt.AlignmentFlag.AlignTop)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)
        layout.addWidget(self.eyebrow_label)
        layout.addLayout(title_row)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_description(self, description: str) -> None:
        self.description_label.setText(description)

    def set_context(self, context: str) -> None:
        self.context_label.setFullText(context)
        self.context_label.setVisible(bool(context.strip()))

    def add_action(self, widget: QWidget) -> None:
        self.action_layout.addWidget(widget)


class SectionCard(QFrame):
    """A softly elevated content section with an internal heading."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        *,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dangerSection" if danger else "sectionCard")

        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        self.body_layout.setSpacing(SPACE_4)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("sectionTitle")
            self.body_layout.addWidget(title_label)

        if description:
            description_label = QLabel(description)
            description_label.setObjectName("sectionDescription")
            description_label.setWordWrap(True)
            self.body_layout.addWidget(description_label)

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        if alignment is None:
            self.body_layout.addWidget(widget, stretch)
        else:
            self.body_layout.addWidget(widget, stretch, alignment)

    def addLayout(self, layout: QLayout, stretch: int = 0) -> None:
        self.body_layout.addLayout(layout, stretch)


class StatusBadge(QFrame):
    """A semantic status indicator that never relies on color alone."""

    def __init__(
        self,
        text: str,
        *,
        tone: str = "success",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statusBadge")
        self.setProperty("tone", tone)

        self.dot = QFrame()
        self.dot.setObjectName("statusDot")
        self.dot.setProperty("tone", tone)
        self.dot.setFixedSize(8, 8)

        self.label = QLabel(text)
        self.label.setObjectName("statusBadgeLabel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_2, SPACE_1, SPACE_2, SPACE_1)
        layout.setSpacing(SPACE_2)
        layout.addWidget(self.dot)
        layout.addWidget(self.label)

    def set_status(self, text: str, tone: str) -> None:
        self.label.setText(text)
        self.setProperty("tone", tone)
        self.dot.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)


class ElidedLabel(QLabel):
    """A metadata label that elides long paths while retaining a full tooltip."""

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setFullText(text)

    def setFullText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elision()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        available_width = max(80, self.width())
        metrics = QFontMetrics(self.font())
        super().setText(
            metrics.elidedText(
                self._full_text,
                Qt.TextElideMode.ElideMiddle,
                available_width,
            )
        )


class ScanningBar(QWidget):
    """A restrained indeterminate progress indicator for USB discovery."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scanningBar")
        self.setFixedSize(240, 6)
        self._position = 0.0
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(1_450)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)

    def start(self) -> None:
        self._animation.start()

    def stop(self) -> None:
        self._animation.stop()
        self._set_position(0.0)

    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float) -> None:
        self._position = value
        self.update()

    position = Property(float, _get_position, _set_position)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 1, self.width(), 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#343434"))
        painter.drawRoundedRect(track, 2, 2)

        segment_width = self.width() * 0.28
        left = (self.width() - segment_width) * self._position
        painter.setBrush(QColor("#c8c8c8"))
        painter.drawRoundedRect(QRectF(left, 1, segment_width, 4), 2, 2)
        painter.end()


class ToastBanner(QFrame):
    """Temporary in-app feedback displayed near the current interaction."""

    MIN_WIDTH = 220
    MAX_WIDTH = 520
    EDGE_OFFSET = 18

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toastBanner")
        self.hide()

        self.label = QLabel()
        self.label.setObjectName("toastText")
        self.label.setWordWrap(True)

        self.activity = QProgressBar()
        self.activity.setObjectName("toastActivity")
        self.activity.setRange(0, 0)
        self.activity.setTextVisible(False)
        self.activity.hide()

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(SPACE_1)
        content.addWidget(self.label)
        content.addWidget(self.activity)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        self._layout.addLayout(content)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, message: str, timeout_ms: int) -> None:
        normalized = message.strip()

        if not normalized:
            return

        self.label.setText(normalized)
        self._apply_content_width()
        self._position()
        self.show()
        self.raise_()

        self._timer.stop()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)

    def set_busy(self, busy: bool) -> None:
        self.activity.setVisible(busy)
        if busy and self.label.text().strip():
            self.adjustSize()
            self._position()
            self.show()
            self.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self._position()
        return super().eventFilter(watched, event)

    def _apply_content_width(self) -> None:
        # A frameless width guess makes Qt wrap word-wrapped labels into a
        # narrow, many-line column. Pick a sane width from the message's
        # natural single-line length first, then let it wrap within that.
        metrics = QFontMetrics(self.label.font())
        text_width = metrics.horizontalAdvance(self.label.text())
        margins = self._layout.contentsMargins()
        chrome = margins.left() + margins.right()
        width = max(self.MIN_WIDTH, min(text_width + chrome, self.MAX_WIDTH))
        self.setFixedWidth(width)
        self.adjustSize()

    def _position(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(SPACE_4, parent.width() - self.width() - self.EDGE_OFFSET)
        y = max(SPACE_4, parent.height() - self.height() - self.EDGE_OFFSET)
        self.move(x, y)


class FeedbackStatusBar(QStatusBar):
    """Preserve status APIs for tests while presenting messages as toasts."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.toast = ToastBanner(parent)
        parent.installEventFilter(self.toast)
        self.setFixedHeight(0)

    def showMessage(self, message: str, timeout: int | None = 0) -> None:
        super().showMessage(message, timeout)
        self.toast.show_message(message, 0 if timeout is None else timeout)

    def set_busy(self, busy: bool) -> None:
        self.toast.set_busy(busy)
