"""Desktop Security Center for USB keys and password rotation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.icons import app_icon
from usb_vault.ui.security_backend import (
    SecuritySnapshot,
)


class SecurityPage(QWidget):
    """Manage registered USB keys and the vault password."""

    refresh_requested = Signal()
    add_key_requested = Signal(str)
    revoke_key_requested = Signal(str)
    password_change_requested = Signal(
        str,
        str,
        object,
        str,
    )
    close_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("securityPage")

        self._additional_keyfile_count = 0
        self._recovery_required = False

        eyebrow = QLabel("SECURITY CENTER")
        eyebrow.setObjectName("securityEyebrow")

        title = QLabel("Vault security")
        title.setObjectName("securityPageTitle")

        subtitle = QLabel(
            "Manage independent USB keys and rotate the password protecting every unlock method."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        key_group = self._create_key_group()
        password_group = self._create_password_group()

        self.error_label = QLabel()
        self.error_label.setObjectName("securityPageErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.close_button = QPushButton("Back to Vault")
        self.close_button.setObjectName("closeSecurityButton")
        self.close_button.setIcon(app_icon("back"))
        self.close_button.clicked.connect(self.close_requested.emit)

        content = QWidget()
        content.setObjectName("securityContent")
        content.setStyleSheet("background: #0b1220;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 30, 34, 28)
        content_layout.setSpacing(10)
        content_layout.addWidget(eyebrow)
        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addSpacing(10)
        content_layout.addWidget(key_group)
        content_layout.addWidget(password_group)
        content_layout.addWidget(self.error_label)
        content_layout.addWidget(self.close_button)
        content_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("securityScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        scroll_area.viewport().setStyleSheet("background: #0b1220;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

    def set_snapshot(
        self,
        snapshot: SecuritySnapshot,
    ) -> None:
        """Display current key and recovery metadata."""
        if not isinstance(
            snapshot,
            SecuritySnapshot,
        ):
            raise TypeError("snapshot must be SecuritySnapshot")

        self._additional_keyfile_count = snapshot.additional_keyfile_count
        self._recovery_required = snapshot.recovery_configured

        self.keys_table.setRowCount(0)

        for key in snapshot.keys:
            row = self.keys_table.rowCount()
            self.keys_table.insertRow(row)

            key_id_item = QTableWidgetItem(key.key_id_hex)
            role_item = QTableWidgetItem("Current" if key.is_current else "Backup")

            self.keys_table.setItem(
                row,
                0,
                key_id_item,
            )
            self.keys_table.setItem(
                row,
                1,
                role_item,
            )

        self.key_count_label.setText(f"{len(snapshot.keys)} registered USB key(s)")

        additional_keys_message = (
            f"Select exactly {self._additional_keyfile_count} additional registered USB keyfile(s)."
        )
        self.additional_keys_label.setText(additional_keys_message)

        self.recovery_code_label.setVisible(self._recovery_required)
        self.recovery_code_edit.setVisible(self._recovery_required)

        self.keys_table.clearSelection()
        self._update_revoke_button()

    def show_error(
        self,
        message: str,
    ) -> None:
        """Display a Security Center error."""
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear the current Security Center error."""
        self.error_label.clear()
        self.error_label.hide()

    def clear_sensitive_fields(
        self,
    ) -> None:
        """Clear passwords, recovery code, and selected keyfile paths."""
        self.current_password_edit.clear()
        self.new_password_edit.clear()
        self.confirmation_edit.clear()
        self.recovery_code_edit.clear()
        self.additional_keyfiles_list.clear()
        self.show_passwords_checkbox.setChecked(False)

    def add_password_keyfile_path(
        self,
        path: str | Path,
    ) -> None:
        """Add one unique additional keyfile path to the list."""
        normalized = str(Path(path))

        existing = {
            self.additional_keyfiles_list.item(index).text()
            for index in range(self.additional_keyfiles_list.count())
        }

        if normalized not in existing:
            self.additional_keyfiles_list.addItem(normalized)

    def selected_key_id_hex(
        self,
    ) -> str | None:
        """Return the selected registered key ID."""
        selected_rows = self.keys_table.selectionModel().selectedRows()

        if not selected_rows:
            return None

        item = self.keys_table.item(
            selected_rows[0].row(),
            0,
        )

        if item is None:
            return None

        return item.text()

    def _create_key_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox("Registered USB Keys")

        self.key_count_label = QLabel()

        self.keys_table = QTableWidget(
            0,
            2,
        )
        self.keys_table.setObjectName("securityKeysTable")
        self.keys_table.setHorizontalHeaderLabels(
            (
                "Key ID",
                "Role",
            )
        )
        self.keys_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.keys_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.keys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.keys_table.verticalHeader().hide()
        self.keys_table.horizontalHeader().setFixedHeight(38)
        self.keys_table.verticalHeader().setDefaultSectionSize(40)
        self.keys_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.keys_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.keys_table.itemSelectionChanged.connect(self._update_revoke_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshSecurityButton")
        self.refresh_button.setIcon(app_icon("refresh"))
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        self.add_key_button = QPushButton("Create backup key")
        self.add_key_button.setObjectName("addSecurityKeyButton")
        self.add_key_button.setIcon(app_icon("key"))
        self.add_key_button.clicked.connect(self._choose_new_keyfile)

        self.revoke_key_button = QPushButton("Revoke Selected")
        self.revoke_key_button.setObjectName("revokeSecurityKeyButton")
        self.revoke_key_button.setIcon(app_icon("trash", "#ffb2b2"))
        self.revoke_key_button.setEnabled(False)
        self.revoke_key_button.clicked.connect(self._emit_revoke)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.add_key_button)
        buttons.addWidget(self.revoke_key_button)
        buttons.addStretch()

        layout = QVBoxLayout(group)
        layout.addWidget(self.key_count_label)
        layout.addWidget(self.keys_table)
        layout.addLayout(buttons)

        return group

    def _create_password_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox("Change Vault Password")

        explanation = QLabel(
            "Every registered USB key must be present "
            "so the same master key can be re-wrapped "
            "under the new password."
        )
        explanation.setWordWrap(True)

        self.current_password_edit = QLineEdit()
        self.current_password_edit.setObjectName("securityCurrentPasswordEdit")
        self.current_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.new_password_edit = QLineEdit()
        self.new_password_edit.setObjectName("securityNewPasswordEdit")
        self.new_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.confirmation_edit = QLineEdit()
        self.confirmation_edit.setObjectName("securityConfirmPasswordEdit")
        self.confirmation_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.show_passwords_checkbox = QCheckBox("Show passwords")
        self.show_passwords_checkbox.setObjectName("showSecurityPasswordsCheckbox")
        self.show_passwords_checkbox.toggled.connect(self._set_passwords_visible)

        self.additional_keys_label = QLabel()
        self.additional_keys_label.setWordWrap(True)

        self.additional_keyfiles_list = QListWidget()
        self.additional_keyfiles_list.setObjectName("additionalPasswordKeyfilesList")
        self.additional_keyfiles_list.setMaximumHeight(110)

        add_existing_button = QPushButton("Select Keyfiles…")
        add_existing_button.setObjectName("selectPasswordKeyfilesButton")
        add_existing_button.setIcon(app_icon("folder"))
        add_existing_button.clicked.connect(self._choose_additional_keyfiles)

        remove_existing_button = QPushButton("Remove Selected")
        remove_existing_button.setObjectName("removePasswordKeyfileButton")
        remove_existing_button.setIcon(app_icon("trash", "#ffb2b2"))
        remove_existing_button.clicked.connect(self._remove_selected_keyfile)

        keyfile_buttons = QHBoxLayout()
        keyfile_buttons.addWidget(add_existing_button)
        keyfile_buttons.addWidget(remove_existing_button)
        keyfile_buttons.addStretch()

        self.recovery_code_label = QLabel("Current recovery code:")
        self.recovery_code_edit = QPlainTextEdit()
        self.recovery_code_edit.setObjectName("securityRecoveryCodeEdit")
        self.recovery_code_edit.setMaximumHeight(85)
        self.recovery_code_edit.setPlaceholderText("Paste the current UVR1 recovery code")

        self.change_password_button = QPushButton("Change Password")
        self.change_password_button.setObjectName("changeSecurityPasswordButton")
        self.change_password_button.setIcon(app_icon("key", "#09201f"))
        self.change_password_button.clicked.connect(self._emit_password_change)

        form = QFormLayout()
        form.addRow(
            "Current password:",
            self.current_password_edit,
        )
        form.addRow(
            "New password:",
            self.new_password_edit,
        )
        form.addRow(
            "Confirm:",
            self.confirmation_edit,
        )
        form.addRow(
            "",
            self.show_passwords_checkbox,
        )

        layout = QVBoxLayout(group)
        layout.addWidget(explanation)
        layout.addLayout(form)
        layout.addWidget(self.additional_keys_label)
        layout.addWidget(self.additional_keyfiles_list)
        layout.addLayout(keyfile_buttons)
        layout.addWidget(self.recovery_code_label)
        layout.addWidget(self.recovery_code_edit)
        layout.addWidget(self.change_password_button)

        return group

    def _choose_new_keyfile(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create backup USB keyfile",
            "",
            ("USB Vault keyfiles (*.authkey);;All files (*)"),
        )

        if selected_path:
            self.add_key_requested.emit(selected_path)

    def _emit_revoke(self) -> None:
        key_id_hex = self.selected_key_id_hex()

        if key_id_hex is not None:
            self.revoke_key_requested.emit(key_id_hex)

    def _choose_additional_keyfiles(
        self,
    ) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select every additional registered USB keyfile",
            "",
            ("USB Vault keyfiles (*.authkey);;All files (*)"),
        )

        for selected_path in selected_paths:
            self.add_password_keyfile_path(selected_path)

    def _remove_selected_keyfile(
        self,
    ) -> None:
        selected_rows = sorted(
            {index.row() for index in (self.additional_keyfiles_list.selectedIndexes())},
            reverse=True,
        )

        for row in selected_rows:
            self.additional_keyfiles_list.takeItem(row)

    def _emit_password_change(
        self,
    ) -> None:
        current_password = self.current_password_edit.text()
        new_password = self.new_password_edit.text()
        confirmation = self.confirmation_edit.text()
        recovery_code = self.recovery_code_edit.toPlainText().strip()
        additional_paths = tuple(
            self.additional_keyfiles_list.item(index).text()
            for index in range(self.additional_keyfiles_list.count())
        )

        if not current_password:
            self.show_error("Enter the current password.")
            return

        if not new_password:
            self.show_error("Enter a new password.")
            return

        if new_password != confirmation:
            self.show_error("New passwords do not match.")
            return

        if new_password == current_password:
            self.show_error("The new password must differ from the current password.")
            return

        if len(additional_paths) != self._additional_keyfile_count:
            message = (
                "Select exactly "
                f"{self._additional_keyfile_count} "
                "additional registered USB keyfile(s)."
            )
            self.show_error(message)
            return

        if self._recovery_required and not recovery_code:
            self.show_error("Enter the current recovery code.")
            return

        self.clear_error()
        self.password_change_requested.emit(
            current_password,
            new_password,
            additional_paths,
            recovery_code,
        )

    def _update_revoke_button(
        self,
    ) -> None:
        selected_rows = self.keys_table.selectionModel().selectedRows()

        if not selected_rows:
            self.revoke_key_button.setEnabled(False)
            return

        role_item = self.keys_table.item(
            selected_rows[0].row(),
            1,
        )

        self.revoke_key_button.setEnabled(role_item is not None and role_item.text() != "Current")

    def _set_passwords_visible(
        self,
        visible: bool,
    ) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password

        self.current_password_edit.setEchoMode(echo_mode)
        self.new_password_edit.setEchoMode(echo_mode)
        self.confirmation_edit.setEchoMode(echo_mode)
