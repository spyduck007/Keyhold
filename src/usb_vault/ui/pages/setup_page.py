"""New-vault setup page."""

from __future__ import annotations

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
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.icons import app_icon


class SetupPage(QWidget):
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
    ) -> None:
        super().__init__(parent)

        self.setObjectName("setupPage")

        eyebrow = QLabel("NEW VAULT")
        eyebrow.setObjectName("setupEyebrow")

        title = QLabel("Create a vault")
        title.setObjectName("setupTitle")

        subtitle = QLabel("Choose separate locations for the encrypted vault and USB keyfile.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setObjectName("newVaultPathEdit")
        self.vault_path_edit.setPlaceholderText("Choose a new .vault file")

        self.keyfile_path_edit = QLineEdit()
        self.keyfile_path_edit.setObjectName("newKeyfilePathEdit")
        self.keyfile_path_edit.setPlaceholderText("Choose a location on the USB")

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

        keyfile_browse_button = QPushButton("Browse…")
        keyfile_browse_button.setObjectName("browseNewKeyfileButton")
        keyfile_browse_button.setIcon(app_icon("key"))
        keyfile_browse_button.clicked.connect(self._browse_keyfile)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit)
        vault_row.addWidget(vault_browse_button)

        keyfile_row = QHBoxLayout()
        keyfile_row.addWidget(self.keyfile_path_edit)
        keyfile_row.addWidget(keyfile_browse_button)

        form = QFormLayout()
        form.addRow(
            "Vault:",
            vault_row,
        )
        form.addRow(
            "USB keyfile:",
            keyfile_row,
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
        surface.setObjectName("formSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(24, 22, 24, 22)
        surface_layout.setSpacing(12)
        surface_layout.addLayout(form)
        surface_layout.addWidget(self.error_label)
        surface_layout.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 28)
        layout.setSpacing(8)
        layout.addStretch()
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addWidget(surface)
        layout.addStretch()

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
        self.keyfile_path_edit.clear()
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
            self.show_error("Choose a location for the USB keyfile.")
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

    def _browse_keyfile(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create USB keyfile",
            "",
            ("USB Vault keyfiles (*.authkey);;All files (*)"),
        )

        if selected_path:
            self.keyfile_path_edit.setText(selected_path)

    def _set_passwords_visible(
        self,
        visible: bool,
    ) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(echo_mode)
        self.confirmation_edit.setEchoMode(echo_mode)
