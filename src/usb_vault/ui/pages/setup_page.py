"""New-vault setup page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from usb_vault.platform.macos.usb_volumes import UsbVolumeLocator
from usb_vault.ui.components import (
    FORM_MAX_WIDTH,
    SPACE_6,
    PageHeader,
    ResponsivePage,
    form_label,
)
from usb_vault.ui.icons import app_icon
from usb_vault.ui.usb_volume_selector import UsbVolumeSelector


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
        super().__init__(
            "setupPage",
            max_width=FORM_MAX_WIDTH,
            parent=parent,
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

        self.usb_volume_selector = UsbVolumeSelector(
            usb_volume_locator=usb_volume_locator,
        )
        self.usb_volume_combo = self.usb_volume_selector.combo
        self.usb_volume_selector.keyfile_path_changed.connect(self.keyfile_path_edit.setText)

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
        self.show_password_checkbox.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Preferred,
        )
        self.show_password_checkbox.toggled.connect(self._set_passwords_visible)

        vault_browse_button = QPushButton("Browse…")
        vault_browse_button.setObjectName("browseNewVaultButton")
        vault_browse_button.setIcon(app_icon("folder"))
        vault_browse_button.clicked.connect(self._browse_vault)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit, 1)
        vault_row.addWidget(vault_browse_button, 0)

        form = QFormLayout()
        form.addRow(
            form_label("Vault file"),
            vault_row,
        )
        form.addRow(
            form_label("USB key"),
            self.usb_volume_selector,
        )
        form.addRow(
            form_label("Keyfile"),
            self.keyfile_path_edit,
        )
        form.addRow(
            form_label("Password"),
            self.password_edit,
        )
        form.addRow(
            form_label("Confirm password"),
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
        self.create_button.setIcon(app_icon("plus", "#181818"))
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
        self.content_layout.addStretch(1)

        self._update_keyfile_path()

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
        self.refresh_usb_volumes()
        self.usb_volume_selector.clear_selection()
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
            ("Keyhold vaults (*.vault);;All files (*)"),
        )

        if selected_path:
            self.vault_path_edit.setText(selected_path)

    def refresh_usb_volumes(self) -> None:
        """Reload mounted external USBs and preserve the current choice."""
        self.usb_volume_selector.refresh_volumes()

    def _selected_usb_volume_path(self) -> Path | None:
        return self.usb_volume_selector.selected_volume_path

    def _update_keyfile_path(self) -> None:
        keyfile_path = self.usb_volume_selector.keyfile_path
        self.keyfile_path_edit.setText(str(keyfile_path) if keyfile_path is not None else "")

    def _set_passwords_visible(
        self,
        visible: bool,
    ) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(echo_mode)
        self.confirmation_edit.setEchoMode(echo_mode)
