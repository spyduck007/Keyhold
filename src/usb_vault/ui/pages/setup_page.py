"""New-vault setup page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from usb_vault.platform.macos.usb_volumes import (
    MacOsUsbVolumeLocator,
    UsbVolumeLocator,
)
from usb_vault.ui.components import FORM_MAX_WIDTH, SPACE_6, PageHeader, ResponsivePage
from usb_vault.ui.icons import app_icon

DEFAULT_USB_KEYFILE_NAME = ".authkey"


class UsbVolumeComboBox(QComboBox):
    """A themed USB selector with a consistent, custom-drawn chevron."""

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(
            QColor("#9baec7" if self.isEnabled() else "#60748c"),
            1.8,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)

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
        painter.end()


class SetupPage(ResponsivePage):
    """Collect locations and a password for a new vault."""

    setup_requested = Signal(
        str,
        str,
        str,
    )
    cancel_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        usb_volume_locator: UsbVolumeLocator | None = None,
    ) -> None:
        super().__init__("setupPage", max_width=FORM_MAX_WIDTH, parent=parent)

        self._usb_volume_locator = (
            usb_volume_locator if usb_volume_locator is not None else MacOsUsbVolumeLocator()
        )

        header = PageHeader(
            "NEW VAULT",
            "Create a vault",
            "Choose a location for the encrypted vault, then select the USB that will hold "
            "its hardware key.",
        )

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setObjectName("newVaultPathEdit")
        self.vault_path_edit.setPlaceholderText("Choose a new .vault file")

        self.keyfile_path_edit = QLineEdit()
        self.keyfile_path_edit.setObjectName("newKeyfilePathEdit")
        self.keyfile_path_edit.setReadOnly(True)
        self.keyfile_path_edit.setPlaceholderText("Select an external USB to create .authkey")

        self.usb_volume_combo = UsbVolumeComboBox()
        self.usb_volume_combo.setObjectName("usbVolumeComboBox")
        self.usb_volume_combo.setPlaceholderText("Select an external USB")
        self.usb_volume_combo.currentIndexChanged.connect(self._update_keyfile_path)

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("newPasswordEdit")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Create a vault password")

        self.confirmation_edit = QLineEdit()
        self.confirmation_edit.setObjectName("confirmPasswordEdit")
        self.confirmation_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation_edit.setPlaceholderText("Repeat the password")

        self.show_password_checkbox = QCheckBox("Show passwords")
        self.show_password_checkbox.setObjectName("showSetupPasswordsCheckbox")
        self.show_password_checkbox.toggled.connect(self._set_passwords_visible)

        vault_browse_button = QPushButton("Browse…")
        vault_browse_button.setObjectName("browseNewVaultButton")
        vault_browse_button.setIcon(app_icon("folder"))
        vault_browse_button.clicked.connect(self._browse_vault)

        refresh_usb_volumes_button = QPushButton("Refresh")
        refresh_usb_volumes_button.setObjectName("refreshUsbVolumesButton")
        refresh_usb_volumes_button.setIcon(app_icon("refresh"))
        refresh_usb_volumes_button.clicked.connect(self.refresh_usb_volumes)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit)
        vault_row.addWidget(vault_browse_button)

        keyfile_row = QHBoxLayout()
        keyfile_row.addWidget(self.usb_volume_combo)
        keyfile_row.addWidget(refresh_usb_volumes_button)

        form = QFormLayout()
        form.addRow(
            "Vault:",
            vault_row,
        )
        form.addRow(
            "USB key:",
            keyfile_row,
        )
        form.addRow(
            "Keyfile:",
            self.keyfile_path_edit,
        )
        form.addRow(
            "Password:",
            self.password_edit,
        )
        form.addRow(
            "Confirm:",
            self.confirmation_edit,
        )
        form.addRow(
            "",
            self.show_password_checkbox,
        )

        self.error_label = QLabel()
        self.error_label.setObjectName("setupErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelSetupButton")
        self.cancel_button.setIcon(app_icon("back"))
        self.cancel_button.clicked.connect(self._cancel)

        self.create_button = QPushButton("Create vault")
        self.create_button.setObjectName("createVaultButton")
        self.create_button.setIcon(app_icon("plus", "#09201f"))
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._emit_setup)
        self.confirmation_edit.returnPressed.connect(self._emit_setup)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        buttons.addWidget(self.create_button)

        surface = QFrame()
        surface.setObjectName("sectionCard")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(24, 22, 24, 22)
        surface_layout.setSpacing(12)
        surface_layout.addLayout(form)
        surface_layout.addWidget(self.error_label)
        surface_layout.addLayout(buttons)

        self.content_layout.setSpacing(SPACE_6)
        self.content_layout.addWidget(header)
        self.content_layout.addWidget(surface)
        self.content_layout.addStretch()

        self.refresh_usb_volumes()

    def show_error(
        self,
        message: str,
    ) -> None:
        """Display a setup error."""
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear the current setup error."""
        self.error_label.clear()
        self.error_label.hide()

    def clear_sensitive_fields(self) -> None:
        """Clear password text held by the widgets."""
        self.password_edit.clear()
        self.confirmation_edit.clear()
        self.show_password_checkbox.setChecked(False)

    def reset(self) -> None:
        """Reset the complete setup form."""
        self.vault_path_edit.clear()
        self.usb_volume_combo.setCurrentIndex(-1)
        self._update_keyfile_path()
        self.clear_sensitive_fields()
        self.clear_error()
        self.vault_path_edit.setFocus()

    def _emit_setup(self) -> None:
        vault_path = self.vault_path_edit.text().strip()
        keyfile_path = self.keyfile_path_edit.text().strip()
        password = self.password_edit.text()
        confirmation = self.confirmation_edit.text()

        if not vault_path:
            self.show_error("Choose a location for the vault.")
            return

        if not keyfile_path:
            self.show_error("Select an external USB for the hardware key.")
            return

        if not password:
            self.show_error("Create a vault password.")
            return

        if password != confirmation:
            self.show_error("Passwords do not match.")
            return

        self.clear_error()
        self.setup_requested.emit(
            vault_path,
            keyfile_path,
            password,
        )

    def _cancel(self) -> None:
        self.reset()
        self.cancel_requested.emit()

    def _browse_vault(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create encrypted vault",
            "",
            ("USB Vault files (*.vault);;All files (*)"),
        )

        if selected_path:
            self.vault_path_edit.setText(selected_path)

    def refresh_usb_volumes(self) -> None:
        """Reload mounted external USBs and preserve the current choice when possible."""
        selected_path = self._selected_usb_volume_path()

        try:
            volume_paths = self._usb_volume_locator.external_usb_volumes()
        except (
            OSError,
            RuntimeError,
            ValueError,
        ):
            volume_paths = ()

        self.usb_volume_combo.blockSignals(True)
        self.usb_volume_combo.clear()
        self.usb_volume_combo.addItem("Select an external USB", None)

        for volume_path in volume_paths:
            self.usb_volume_combo.addItem(
                volume_path.name,
                str(volume_path),
            )

        if selected_path is not None:
            selected_index = self.usb_volume_combo.findData(str(selected_path))
            self.usb_volume_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        else:
            self.usb_volume_combo.setCurrentIndex(0)

        self.usb_volume_combo.setEnabled(bool(volume_paths))
        self.usb_volume_combo.blockSignals(False)
        self._update_keyfile_path()

    def _selected_usb_volume_path(self) -> Path | None:
        selected_path = self.usb_volume_combo.currentData()
        return Path(selected_path) if isinstance(selected_path, str) else None

    def _update_keyfile_path(self) -> None:
        selected_path = self._selected_usb_volume_path()
        keyfile_path = (
            selected_path / DEFAULT_USB_KEYFILE_NAME if selected_path is not None else None
        )
        self.keyfile_path_edit.setText(str(keyfile_path) if keyfile_path is not None else "")

    def _set_passwords_visible(
        self,
        visible: bool,
    ) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(echo_mode)
        self.confirmation_edit.setEchoMode(echo_mode)
