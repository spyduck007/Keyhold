"""Unlock screen for an existing vault."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class UnlockPage(QWidget):
    """Collect a vault, USB keyfile, and password."""

    unlock_requested = Signal(
        str,
        str,
        str,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("unlockPage")

        title = QLabel("Unlock USB Vault")
        title.setObjectName("unlockTitle")

        subtitle = QLabel("Choose the encrypted vault and the keyfile stored on your USB.")
        subtitle.setWordWrap(True)

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setObjectName("vaultPathEdit")
        self.vault_path_edit.setPlaceholderText("Select a .vault file")

        self.keyfile_path_edit = QLineEdit()
        self.keyfile_path_edit.setObjectName("keyfilePathEdit")
        self.keyfile_path_edit.setPlaceholderText("Select the USB .authkey file")

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("passwordEdit")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Vault password")

        self.show_password_checkbox = QCheckBox("Show password")
        self.show_password_checkbox.setObjectName("showPasswordCheckbox")
        self.show_password_checkbox.toggled.connect(self._set_password_visible)

        vault_browse_button = QPushButton("Browse…")
        vault_browse_button.setObjectName("browseVaultButton")
        vault_browse_button.clicked.connect(self._browse_vault)

        keyfile_browse_button = QPushButton("Browse…")
        keyfile_browse_button.setObjectName("browseKeyfileButton")
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
            "",
            self.show_password_checkbox,
        )

        self.error_label = QLabel()
        self.error_label.setObjectName("unlockErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.unlock_button = QPushButton("Unlock")
        self.unlock_button.setObjectName("unlockButton")
        self.unlock_button.setDefault(True)
        self.unlock_button.clicked.connect(self._emit_unlock)
        self.password_edit.returnPressed.connect(self._emit_unlock)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.unlock_button)
        layout.addStretch()

    def show_error(
        self,
        message: str,
    ) -> None:
        """Display an unlock or validation error."""
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear the current error message."""
        self.error_label.clear()
        self.error_label.hide()

    def clear_password(self) -> None:
        """Clear password text held by the widget."""
        self.password_edit.clear()
        self.show_password_checkbox.setChecked(False)

    def reset_after_lock(self) -> None:
        """Return the page to a safe locked state."""
        self.clear_password()
        self.clear_error()
        self.password_edit.setFocus()

    def _emit_unlock(self) -> None:
        vault_path = self.vault_path_edit.text().strip()
        keyfile_path = self.keyfile_path_edit.text().strip()
        password = self.password_edit.text()

        if not vault_path:
            self.show_error("Choose a vault file.")
            return

        if not keyfile_path:
            self.show_error("Choose a USB keyfile.")
            return

        if not password:
            self.show_error("Enter the vault password.")
            return

        self.clear_error()
        self.unlock_requested.emit(
            vault_path,
            keyfile_path,
            password,
        )

    def _browse_vault(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open encrypted vault",
            "",
            ("USB Vault files (*.vault);;All files (*)"),
        )

        if selected_path:
            self.vault_path_edit.setText(selected_path)

    def _browse_keyfile(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select USB keyfile",
            "",
            ("USB Vault keyfiles (*.authkey);;All files (*)"),
        )

        if selected_path:
            self.keyfile_path_edit.setText(selected_path)

    def _set_password_visible(
        self,
        visible: bool,
    ) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(echo_mode)
