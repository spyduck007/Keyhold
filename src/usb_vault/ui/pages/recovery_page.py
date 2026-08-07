"""Desktop workflow for restoring USB access."""

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
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.components import FORM_MAX_WIDTH, SPACE_6, PageHeader, ResponsivePage
from usb_vault.ui.icons import app_icon


class RecoveryPage(ResponsivePage):
    """Collect credentials needed to create a replacement USB key."""

    recovery_requested = Signal(
        str,
        str,
        str,
        str,
        bool,
    )
    cancel_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("recoveryPage", max_width=FORM_MAX_WIDTH, parent=parent)

        header = PageHeader(
            "RECOVERY",
            "Restore USB access",
            "Use your vault password and offline recovery code to register a replacement USB key.",
        )

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setObjectName("recoveryVaultPathEdit")
        self.vault_path_edit.setPlaceholderText("Select the encrypted .vault file")

        self.new_keyfile_path_edit = QLineEdit()
        self.new_keyfile_path_edit.setObjectName("recoveryNewKeyfilePathEdit")
        self.new_keyfile_path_edit.setPlaceholderText("Choose a path on the replacement USB")

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("recoveryPasswordEdit")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Vault password")

        self.confirmation_edit = QLineEdit()
        self.confirmation_edit.setObjectName("recoveryPasswordConfirmationEdit")
        self.confirmation_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation_edit.setPlaceholderText("Repeat the vault password")

        self.show_password_checkbox = QCheckBox("Show passwords")
        self.show_password_checkbox.setObjectName("showRecoveryPasswordsCheckbox")
        self.show_password_checkbox.toggled.connect(self._set_passwords_visible)

        self.recovery_code_edit = QPlainTextEdit()
        self.recovery_code_edit.setObjectName("recoveryCodeInput")
        self.recovery_code_edit.setPlaceholderText("Paste the current UVR1 recovery code")
        self.recovery_code_edit.setMaximumHeight(90)

        self.replace_existing_keys_checkbox = QCheckBox("Revoke all previous USB keys")
        self.replace_existing_keys_checkbox.setObjectName("replaceExistingKeysCheckbox")
        self.replace_existing_keys_checkbox.setChecked(True)
        self.replace_existing_keys_checkbox.setToolTip(
            "Recommended when the original USB was lost or may be accessible to someone else."
        )

        vault_browse_button = QPushButton("Browse…")
        vault_browse_button.setObjectName("browseRecoveryVaultButton")
        vault_browse_button.setIcon(app_icon("folder"))
        vault_browse_button.clicked.connect(self._browse_vault)

        keyfile_browse_button = QPushButton("Browse…")
        keyfile_browse_button.setObjectName("browseRecoveryKeyfileButton")
        keyfile_browse_button.setIcon(app_icon("key"))
        keyfile_browse_button.clicked.connect(self._browse_new_keyfile)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit)
        vault_row.addWidget(vault_browse_button)

        keyfile_row = QHBoxLayout()
        keyfile_row.addWidget(self.new_keyfile_path_edit)
        keyfile_row.addWidget(keyfile_browse_button)

        form = QFormLayout()
        form.addRow(
            "Vault:",
            vault_row,
        )
        form.addRow(
            "Replacement USB:",
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
        form.addRow(
            "Recovery code:",
            self.recovery_code_edit,
        )
        form.addRow(
            "",
            self.replace_existing_keys_checkbox,
        )

        warning = QLabel(
            "A new recovery code will be generated. "
            "The code used for this recovery will stop working."
        )
        warning.setObjectName("recoveryRotationWarning")
        warning.setWordWrap(True)

        self.error_label = QLabel()
        self.error_label.setObjectName("recoveryPageErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelRecoveryButton")
        self.cancel_button.setIcon(app_icon("back"))
        self.cancel_button.clicked.connect(self._cancel)

        self.recover_button = QPushButton("Recover vault")
        self.recover_button.setObjectName("recoverVaultButton")
        self.recover_button.setIcon(app_icon("shield", "#09201f"))
        self.recover_button.setDefault(True)
        self.recover_button.clicked.connect(self._emit_recovery)
        self.confirmation_edit.returnPressed.connect(self._emit_recovery)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        buttons.addWidget(self.recover_button)

        surface = QFrame()
        surface.setObjectName("sectionCard")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(24, 22, 24, 22)
        surface_layout.setSpacing(12)
        surface_layout.addLayout(form)
        surface_layout.addWidget(warning)
        surface_layout.addWidget(self.error_label)
        surface_layout.addLayout(buttons)

        self.content_layout.setSpacing(SPACE_6)
        self.content_layout.addWidget(header)
        self.content_layout.addWidget(surface)
        self.content_layout.addStretch()

    def show_error(
        self,
        message: str,
    ) -> None:
        """Display a recovery error."""
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear the current recovery error."""
        self.error_label.clear()
        self.error_label.hide()

    def clear_sensitive_fields(self) -> None:
        """Clear credentials held by the recovery widgets."""
        self.password_edit.clear()
        self.confirmation_edit.clear()
        self.recovery_code_edit.clear()
        self.show_password_checkbox.setChecked(False)

    def reset(self) -> None:
        """Reset the complete recovery form."""
        self.vault_path_edit.clear()
        self.new_keyfile_path_edit.clear()
        self.clear_sensitive_fields()
        self.clear_error()
        self.replace_existing_keys_checkbox.setChecked(True)
        self.vault_path_edit.setFocus()

    def _emit_recovery(self) -> None:
        vault_path = self.vault_path_edit.text().strip()
        new_keyfile_path = self.new_keyfile_path_edit.text().strip()
        password = self.password_edit.text()
        confirmation = self.confirmation_edit.text()
        recovery_code = self.recovery_code_edit.toPlainText().strip()

        if not vault_path:
            self.show_error("Choose the encrypted vault.")
            return

        if not new_keyfile_path:
            self.show_error("Choose a path for the replacement USB keyfile.")
            return

        if not password:
            self.show_error("Enter the vault password.")
            return

        if password != confirmation:
            self.show_error("Passwords do not match.")
            return

        if not recovery_code:
            self.show_error("Enter the current recovery code.")
            return

        self.clear_error()
        self.recovery_requested.emit(
            vault_path,
            new_keyfile_path,
            password,
            recovery_code,
            (self.replace_existing_keys_checkbox.isChecked()),
        )

    def _cancel(self) -> None:
        self.reset()
        self.cancel_requested.emit()

    def _browse_vault(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select encrypted vault",
            "",
            ("USB Vault files (*.vault);;All files (*)"),
        )

        if selected_path:
            self.vault_path_edit.setText(selected_path)

    def _browse_new_keyfile(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create replacement USB keyfile",
            "",
            ("USB Vault keyfiles (*.authkey);;All files (*)"),
        )

        if selected_path:
            self.new_keyfile_path_edit.setText(selected_path)

    def _set_passwords_visible(
        self,
        visible: bool,
    ) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(echo_mode)
        self.confirmation_edit.setEchoMode(echo_mode)
