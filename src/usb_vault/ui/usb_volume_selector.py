"""Reusable mounted-USB selector for root-level hardware keyfiles."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from usb_vault.platform.macos.usb_volumes import (
    MacOsUsbVolumeLocator,
    UsbVolumeLocator,
)
from usb_vault.ui.icons import app_icon

DEFAULT_USB_KEYFILE_NAME = ".authkey"


class UsbVolumeComboBox(QComboBox):
    """A themed USB selector with a consistent custom-drawn chevron."""

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor("#bdbdbd" if self.isEnabled() else "#5f5f5f"),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )

        center_x = self.width() - 17
        center_y = self.height() / 2
        painter.drawLine(
            QPointF(center_x - 4, center_y - 2),
            QPointF(center_x, center_y + 2),
        )
        painter.drawLine(
            QPointF(center_x, center_y + 2),
            QPointF(center_x + 4, center_y - 2),
        )


class UsbVolumeSelector(QWidget):
    """Select a mounted external USB and resolve its root ``.authkey`` path."""

    keyfile_path_changed = Signal(str)

    def __init__(
        self,
        *,
        usb_volume_locator: UsbVolumeLocator | None = None,
        placeholder: str = "Select an external USB",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._usb_volume_locator = (
            usb_volume_locator if usb_volume_locator is not None else MacOsUsbVolumeLocator()
        )
        self._placeholder = placeholder

        self.combo = UsbVolumeComboBox()
        self.combo.setObjectName("usbVolumeComboBox")
        self.combo.setToolTip(
            "Keyhold stores the hidden .authkey file at the root of the selected USB."
        )
        self.combo.currentIndexChanged.connect(self._emit_keyfile_path)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshUsbVolumesButton")
        self.refresh_button.setIcon(app_icon("refresh"))
        self.refresh_button.clicked.connect(self.refresh_volumes)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.refresh_button)

        self.refresh_volumes()

    @property
    def selected_volume_path(self) -> Path | None:
        """Return the selected external-volume root, if any."""
        selected_path = self.combo.currentData()
        return Path(selected_path) if isinstance(selected_path, str) else None

    @property
    def keyfile_path(self) -> Path | None:
        """Return the selected volume's canonical root-level keyfile path."""
        volume_path = self.selected_volume_path
        return volume_path / DEFAULT_USB_KEYFILE_NAME if volume_path is not None else None

    def refresh_volumes(self) -> None:
        """Reload mounted external USBs and preserve the current choice."""
        selected_path = self.selected_volume_path

        try:
            volume_paths = self._usb_volume_locator.external_usb_volumes()
        except (OSError, RuntimeError, ValueError):
            volume_paths = ()

        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(self._placeholder, None)

        for volume_path in volume_paths:
            self.combo.addItem(volume_path.name, str(volume_path))

        if selected_path is not None:
            selected_index = self.combo.findData(str(selected_path))
            self.combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        else:
            self.combo.setCurrentIndex(0)

        self.combo.setEnabled(bool(volume_paths))
        self.combo.blockSignals(False)
        self._emit_keyfile_path()

    def clear_selection(self) -> None:
        """Return the selector to its placeholder item."""
        self.combo.setCurrentIndex(0)

    def _emit_keyfile_path(self) -> None:
        keyfile_path = self.keyfile_path
        self.keyfile_path_changed.emit(str(keyfile_path) if keyfile_path is not None else "")
