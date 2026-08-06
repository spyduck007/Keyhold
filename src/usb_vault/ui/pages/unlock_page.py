"""Unlock screen for an existing vault."""

from __future__ import annotations

from PySide6.QtCore import (
    Signal,
)
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
    """Collect a vault, optional keyfile, and password."""

    unlock_requested = Signal(
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

        self.setObjectName("unlockPage")

        self._waiting_for_usb = False
        self._unlocking = False

        title = QLabel("Unlock USB Vault")
        title.setObjectName("unlockTitle")

        subtitle = QLabel(
            "Enter the vault password and "
            "continue. The app will wait for "
            "a registered USB key and unlock "
            "automatically when it appears."
        )
        subtitle.setWordWrap(True)

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setObjectName("vaultPathEdit")
        self.vault_path_edit.setPlaceholderText("Select a .vault file")

        self.keyfile_path_edit = QLineEdit()
        self.keyfile_path_edit.setObjectName("keyfilePathEdit")
        self.keyfile_path_edit.setPlaceholderText("Optional manual keyfile path")
        self.keyfile_path_edit.setToolTip("Leave blank to wait for a registered mounted USB key.")

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("passwordEdit")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Vault password")

        self.show_password_checkbox = QCheckBox("Show password")
        self.show_password_checkbox.setObjectName("showPasswordCheckbox")
        self.show_password_checkbox.toggled.connect(self._set_password_visible)

        self.vault_browse_button = QPushButton("Browse…")
        self.vault_browse_button.setObjectName("browseVaultButton")
        self.vault_browse_button.clicked.connect(self._browse_vault)

        self.keyfile_browse_button = QPushButton("Browse manually…")
        self.keyfile_browse_button.setObjectName("browseKeyfileButton")
        self.keyfile_browse_button.clicked.connect(self._browse_keyfile)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit)
        vault_row.addWidget(self.vault_browse_button)

        keyfile_row = QHBoxLayout()
        keyfile_row.addWidget(self.keyfile_path_edit)
        keyfile_row.addWidget(self.keyfile_browse_button)

        form = QFormLayout()
        form.addRow(
            "Vault:",
            vault_row,
        )
        form.addRow(
            "USB keyfile (optional):",
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

        self.waiting_label = QLabel()
        self.waiting_label.setObjectName("usbUnlockWaitingLabel")
        self.waiting_label.setWordWrap(True)
        self.waiting_label.hide()

        self.error_label = QLabel()
        self.error_label.setObjectName("unlockErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.cancel_button = QPushButton("Back to Vaults")
        self.cancel_button.setObjectName("cancelUnlockButton")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

        self.unlock_button = QPushButton("Continue")
        self.unlock_button.setObjectName("unlockButton")
        self.unlock_button.setDefault(True)
        self.unlock_button.clicked.connect(self._emit_unlock)
        self.password_edit.returnPressed.connect(self._emit_unlock)

        actions = QHBoxLayout()
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.unlock_button)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addLayout(form)
        layout.addWidget(self.waiting_label)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)
        layout.addStretch()

    @property
    def is_waiting_for_usb(self) -> bool:
        """Return whether the page is waiting for a mounted key."""
        return self._waiting_for_usb

    @property
    def is_unlocking(self) -> bool:
        """Return whether authenticated unlock is running."""
        return self._unlocking

    def begin_waiting_for_usb(
        self,
    ) -> None:
        """Switch the form into cancellable USB-waiting state."""
        self._waiting_for_usb = True
        self._unlocking = False

        self._set_form_enabled(False)

        self.waiting_label.setText(
            (
                "Waiting for a registered "
                "USB key. Insert the key now. "
                "Wrong or unrelated USB keys "
                "will be ignored."
            )
        )
        self.waiting_label.show()

        self.unlock_button.setText("Waiting for USB…")
        self.unlock_button.setEnabled(False)

        self.cancel_button.setText("Cancel")
        self.cancel_button.setEnabled(True)

    def begin_unlocking(
        self,
    ) -> None:
        """Show that a detected key is being authenticated."""
        self._waiting_for_usb = False
        self._unlocking = True

        self._set_form_enabled(False)

        self.waiting_label.setText(("Registered USB key detected. Unlocking the vault…"))
        self.waiting_label.show()

        self.unlock_button.setText("Unlocking…")
        self.unlock_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def end_waiting(self) -> None:
        """Restore the editable password form."""
        self._waiting_for_usb = False
        self._unlocking = False

        self._set_form_enabled(True)

        self.waiting_label.clear()
        self.waiting_label.hide()

        self.unlock_button.setText("Continue")
        self.unlock_button.setEnabled(True)

        self.cancel_button.setText("Back to Vaults")
        self.cancel_button.setEnabled(True)

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
        self.end_waiting()
        self.clear_password()
        self.clear_error()
        self.password_edit.setFocus()

    def _emit_unlock(self) -> None:
        if self._waiting_for_usb or self._unlocking:
            return

        vault_path = self.vault_path_edit.text().strip()
        keyfile_path = self.keyfile_path_edit.text().strip()
        password = self.password_edit.text()

        if not vault_path:
            self.show_error("Choose a vault file.")
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

    def _set_form_enabled(
        self,
        enabled: bool,
    ) -> None:
        for widget in (
            self.vault_path_edit,
            self.keyfile_path_edit,
            self.password_edit,
            self.show_password_checkbox,
            self.vault_browse_button,
            self.keyfile_browse_button,
        ):
            widget.setEnabled(enabled)
