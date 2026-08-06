"""Unlock screen for an existing vault."""

from __future__ import annotations

from PySide6.QtCore import (
    QSize,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.icons import app_icon
from usb_vault.ui.usb_key_animation import UsbKeyAnimation


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
        self._selected_vault_name: str | None = None

        self.eyebrow = QLabel("SECURE ACCESS")
        self.eyebrow.setObjectName("unlockEyebrow")

        self.title = QLabel("Unlock a vault")
        self.title.setObjectName("unlockTitle")

        self.subtitle = QLabel(
            "Enter the vault password and "
            "continue. The app will wait for "
            "a registered USB key and unlock "
            "automatically when it appears."
        )
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)

        self.selected_vault_label = QLabel()
        self.selected_vault_label.setObjectName("selectedVaultLabel")
        self.selected_vault_label.hide()

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
        self.vault_browse_button.setIcon(app_icon("folder"))
        self.vault_browse_button.clicked.connect(self._browse_vault)

        self.keyfile_browse_button = QPushButton("Browse manually…")
        self.keyfile_browse_button.setObjectName("browseKeyfileButton")
        self.keyfile_browse_button.setIcon(app_icon("key"))
        self.keyfile_browse_button.clicked.connect(self._browse_keyfile)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit)
        vault_row.addWidget(self.vault_browse_button)

        keyfile_row = QHBoxLayout()
        keyfile_row.addWidget(self.keyfile_path_edit)
        keyfile_row.addWidget(self.keyfile_browse_button)

        self.vault_selection_row = QWidget()
        vault_selection_layout = QVBoxLayout(self.vault_selection_row)
        vault_selection_layout.setContentsMargins(0, 0, 0, 0)
        vault_selection_layout.addWidget(QLabel("Vault file"))
        vault_selection_layout.addLayout(vault_row)

        self.manual_keyfile_row = QWidget()
        manual_keyfile_layout = QVBoxLayout(self.manual_keyfile_row)
        manual_keyfile_layout.setContentsMargins(0, 0, 0, 0)
        manual_keyfile_layout.addWidget(QLabel("USB keyfile (optional)"))
        manual_keyfile_layout.addLayout(keyfile_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.addRow(
            "Vault password",
            self.password_edit,
        )
        form.addRow(
            "",
            self.show_password_checkbox,
        )

        self.waiting_label = QLabel()
        self.waiting_label.setObjectName("usbUnlockWaitingLabel")
        self.waiting_label.setWordWrap(True)
        self.waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_label.hide()

        self.error_label = QLabel()
        self.error_label.setObjectName("unlockErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.cancel_button = QPushButton("Back to vaults")
        self.cancel_button.setObjectName("cancelUnlockButton")
        self.cancel_button.setIcon(app_icon("back"))
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

        self.unlock_button = QPushButton("Continue")
        self.unlock_button.setObjectName("unlockButton")
        self.unlock_button.setIcon(app_icon("arrow_right", "#09201f"))
        self.unlock_button.setIconSize(QSize(18, 18))
        self.unlock_button.setDefault(True)
        self.unlock_button.clicked.connect(self._emit_unlock)
        self.password_edit.returnPressed.connect(self._emit_unlock)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.unlock_button)

        self.form_surface = QFrame()
        self.form_surface.setObjectName("formSurface")
        form_layout = QVBoxLayout(self.form_surface)
        form_layout.setContentsMargins(24, 22, 24, 22)
        form_layout.setSpacing(12)
        form_layout.addWidget(self.selected_vault_label)
        form_layout.addWidget(self.vault_selection_row)
        form_layout.addWidget(self.manual_keyfile_row)
        form_layout.addLayout(form)
        form_layout.addWidget(self.error_label)
        form_layout.addSpacing(4)
        form_layout.addLayout(actions)

        self.wait_surface = QFrame()
        self.wait_surface.setObjectName("waitSurface")
        self.wait_surface.hide()

        self.wait_animation = UsbKeyAnimation()
        self.waiting_heading = QLabel("Waiting for your USB key")
        self.waiting_heading.setObjectName("unlockTitle")
        self.waiting_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_detail = QLabel(
            "Insert any registered USB key to finish unlocking this vault."
        )
        self.waiting_detail.setObjectName("keyWaitDetail")
        self.waiting_detail.setWordWrap(True)
        self.waiting_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wait_progress = QProgressBar()
        self.wait_progress.setObjectName("usbWaitProgress")
        self.wait_progress.setRange(0, 0)
        self.wait_progress.setTextVisible(False)
        self.wait_progress.setFixedWidth(280)
        self.wait_cancel_button = QPushButton("Cancel")
        self.wait_cancel_button.setObjectName("cancelWaitingUnlockButton")
        self.wait_cancel_button.setIcon(app_icon("back"))
        self.wait_cancel_button.clicked.connect(self.cancel_requested.emit)

        wait_layout = QVBoxLayout(self.wait_surface)
        wait_layout.setContentsMargins(34, 28, 34, 26)
        wait_layout.setSpacing(10)
        wait_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wait_layout.addWidget(self.wait_animation, 0, Qt.AlignmentFlag.AlignCenter)
        wait_layout.addWidget(self.waiting_heading)
        wait_layout.addWidget(self.waiting_detail)
        wait_layout.addWidget(self.waiting_label)
        wait_layout.addWidget(self.wait_progress, 0, Qt.AlignmentFlag.AlignCenter)
        wait_layout.addSpacing(8)
        wait_layout.addWidget(self.wait_cancel_button, 0, Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 28)
        layout.setSpacing(8)
        layout.addStretch()
        layout.addWidget(self.eyebrow)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(12)
        layout.addWidget(self.form_surface)
        layout.addWidget(self.wait_surface)
        layout.addStretch()

    @property
    def is_waiting_for_usb(self) -> bool:
        """Return whether the page is waiting for a mounted key."""
        return self._waiting_for_usb

    @property
    def is_unlocking(self) -> bool:
        """Return whether authenticated unlock is running."""
        return self._unlocking

    def set_selected_vault(self, display_name: str) -> None:
        """Present a card-selected vault as a focused password step."""
        self._selected_vault_name = display_name.strip() or "vault"
        self.title.setText(f"Unlock {self._selected_vault_name}")
        self.subtitle.setText("Enter the vault password to continue securely.")
        self.selected_vault_label.setText("USB key is requested in the next step")
        self.selected_vault_label.show()
        self.vault_selection_row.hide()
        self.manual_keyfile_row.hide()

    def clear_selected_vault(self) -> None:
        """Restore the generic unlock form for direct/manual navigation."""
        self._selected_vault_name = None
        self.title.setText("Unlock a vault")
        self.subtitle.setText(
            "Enter the vault password and continue. The app will wait for a registered USB key "
            "and unlock automatically when it appears."
        )
        self.selected_vault_label.hide()
        self.vault_selection_row.show()
        self.manual_keyfile_row.show()

    def begin_waiting_for_usb(
        self,
    ) -> None:
        """Switch the form into cancellable USB-waiting state."""
        self._waiting_for_usb = True
        self._unlocking = False

        self._set_form_enabled(False)
        self.eyebrow.hide()
        self.title.hide()
        self.subtitle.hide()
        self.form_surface.hide()
        self.wait_surface.show()
        self.wait_animation.start()

        waiting_message = "Scanning connected drives. Unrelated USB keys are ignored automatically."
        self.waiting_label.setText(waiting_message)
        self.waiting_label.show()

        self.unlock_button.setText("Waiting for USB…")
        self.unlock_button.setEnabled(False)

        self.cancel_button.setText("Cancel")
        self.cancel_button.setEnabled(True)
        self.wait_cancel_button.setEnabled(True)

    def begin_unlocking(
        self,
    ) -> None:
        """Show that a detected key is being authenticated."""
        self._waiting_for_usb = False
        self._unlocking = True

        self._set_form_enabled(False)
        self.eyebrow.hide()
        self.title.hide()
        self.subtitle.hide()
        self.form_surface.hide()
        self.wait_surface.show()
        self.wait_cancel_button.setEnabled(False)
        self.wait_animation.stop()
        self.waiting_heading.setText("Validating your USB key")
        self.waiting_detail.setText("Checking key registration and opening the encrypted vault.")

        self.waiting_label.setText("Registered USB key detected. Unlocking the vault…")
        self.waiting_label.show()

        self.unlock_button.setText("Unlocking…")
        self.unlock_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def end_waiting(self) -> None:
        """Restore the editable password form."""
        self._waiting_for_usb = False
        self._unlocking = False

        self._set_form_enabled(True)
        self.eyebrow.show()
        self.title.show()
        self.subtitle.show()
        self.wait_animation.stop()
        self.wait_surface.hide()
        self.form_surface.show()

        self.waiting_label.clear()
        self.waiting_label.hide()
        self.waiting_heading.setText("Waiting for your USB key")
        self.waiting_detail.setText("Insert any registered USB key to finish unlocking this vault.")

        self.unlock_button.setText("Continue")
        self.unlock_button.setEnabled(True)

        self.cancel_button.setText("Back to vaults")
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
