"""Polished Security Center for USB keys and password rotation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.components import (
    CONTENT_MAX_WIDTH,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
    PageHeader,
    ResponsivePage,
    SectionCard,
)
from usb_vault.ui.icons import app_icon
from usb_vault.ui.security_backend import SecuritySnapshot


class MaskedRecoveryCodeEdit(QLineEdit):
    """Single-line masked recovery input with legacy plain-text helpers."""

    def setPlainText(self, text: str) -> None:
        self.setText(text)

    def toPlainText(self) -> str:
        return self.text()


class SecurityPage(QWidget):
    """Manage registered USB keys and rotate the vault password."""

    refresh_requested = Signal()
    add_key_requested = Signal(str)
    revoke_key_requested = Signal(str)
    password_change_requested = Signal(str, str, object, str)
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("securityPage")
        self._additional_keyfile_count = 0
        self._recovery_required = False

        responsive = ResponsivePage("securityContent", max_width=CONTENT_MAX_WIDTH)
        self.header = PageHeader(
            "SECURITY CENTER",
            "Vault security",
            "Manage USB unlock keys and change this vault's password.",
        )

        self.close_button = QPushButton("Back to vault")
        self.close_button.setObjectName("closeSecurityButton")
        self.close_button.setIcon(app_icon("back"))
        self.close_button.clicked.connect(self.close_requested.emit)
        self.header.add_action(self.close_button)

        self.error_label = QLabel()
        self.error_label.setObjectName("securityPageErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        key_section = self._create_key_section()
        password_section = self._create_password_section()

        responsive.content_layout.setSpacing(SPACE_6)
        responsive.content_layout.addWidget(self.header)
        responsive.content_layout.addWidget(self.error_label)
        responsive.content_layout.addWidget(key_section)
        responsive.content_layout.addWidget(password_section)
        responsive.content_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("securityScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(responsive)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

    def set_vault_context(self, vault_path: str) -> None:
        path = Path(vault_path)
        self.header.set_title(f"{path.stem or 'Vault'} security")
        self.header.set_context(vault_path)

    def set_snapshot(self, snapshot: SecuritySnapshot) -> None:
        if not isinstance(snapshot, SecuritySnapshot):
            raise TypeError("snapshot must be SecuritySnapshot")

        self._additional_keyfile_count = snapshot.additional_keyfile_count
        self._recovery_required = snapshot.recovery_configured
        self.keys_table.setSortingEnabled(False)
        self.keys_table.setRowCount(0)

        backup_number = 0
        for key in snapshot.keys:
            row = self.keys_table.rowCount()
            self.keys_table.insertRow(row)
            if key.is_current:
                key_label = "Connected USB key"
                role = "Connected"
            else:
                backup_number += 1
                key_label = f"Backup USB key {backup_number}"
                role = "Backup"

            short_id = _short_key_id(key.key_id_hex)
            key_item = QTableWidgetItem()
            key_item.setData(Qt.ItemDataRole.UserRole, key.key_id_hex)
            key_item.setToolTip(f"Full key ID: {key.key_id_hex}")

            key_cell = QWidget()
            key_cell.setObjectName("keyTableCell")
            key_cell.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            key_name_label = QLabel(key_label)
            key_name_label.setObjectName("keyTableLabel")
            key_id_label = QLabel(short_id)
            key_id_label.setObjectName("keyTableId")
            key_id_label.setToolTip(f"Full key ID: {key.key_id_hex}")
            key_cell_layout = QVBoxLayout(key_cell)
            key_cell_layout.setContentsMargins(SPACE_3, SPACE_1, SPACE_3, SPACE_1)
            key_cell_layout.setSpacing(0)
            key_cell_layout.addWidget(key_name_label)
            key_cell_layout.addWidget(key_id_label)

            role_item = QTableWidgetItem(role)
            role_item.setData(Qt.ItemDataRole.UserRole, key.is_current)
            self.keys_table.setItem(row, 0, key_item)
            self.keys_table.setItem(row, 1, role_item)
            self.keys_table.setCellWidget(row, 0, key_cell)

        key_count = len(snapshot.keys)
        noun = "key" if key_count == 1 else "keys"
        self.key_count_label.setText(f"{key_count} registered USB {noun}")
        self.keys_table.setFixedHeight(min(320, max(108, 42 + key_count * 64)))

        needs_additional_keys = self._additional_keyfile_count > 0
        if needs_additional_keys:
            noun = "key" if self._additional_keyfile_count == 1 else "keys"
            self.additional_keys_label.setText(
                f"Connect and select the other {self._additional_keyfile_count} registered USB "
                f"{noun} before continuing. Changing the password updates every registered key."
            )
        self.additional_keys_widget.setVisible(needs_additional_keys)

        self.recovery_widget.setVisible(self._recovery_required)
        self.keys_table.clearSelection()
        self._update_revoke_button()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def clear_sensitive_fields(self) -> None:
        self.current_password_edit.clear()
        self.new_password_edit.clear()
        self.confirmation_edit.clear()
        self.recovery_code_edit.clear()
        self.additional_keyfiles_list.clear()
        self.show_passwords_checkbox.setChecked(False)
        self.show_recovery_checkbox.setChecked(False)

    def add_password_keyfile_path(self, path: str | Path) -> None:
        normalized = str(Path(path))
        existing = {
            self.additional_keyfiles_list.item(index).text()
            for index in range(self.additional_keyfiles_list.count())
        }
        if normalized not in existing:
            self.additional_keyfiles_list.addItem(normalized)

    def selected_key_id_hex(self) -> str | None:
        selected_rows = self.keys_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        item = self.keys_table.item(selected_rows[0].row(), 0)
        if item is None:
            return None
        key_id = item.data(Qt.ItemDataRole.UserRole)
        return key_id if isinstance(key_id, str) else None

    def _create_key_section(self) -> SectionCard:
        section = SectionCard(
            "USB keys",
            "USB keys complete authentication after password verification. Keep at least one "
            "working backup in a safe place.",
        )

        self.key_count_label = QLabel("Loading registered USB keys…")
        self.key_count_label.setObjectName("metadataText")
        self.keys_table = QTableWidget(0, 2)
        self.keys_table.setObjectName("securityKeysTable")
        self.keys_table.setHorizontalHeaderLabels(("USB key", "Status"))
        self.keys_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.keys_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.keys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.keys_table.setShowGrid(False)
        self.keys_table.verticalHeader().hide()
        self.keys_table.verticalHeader().setDefaultSectionSize(64)
        self.keys_table.horizontalHeader().setFixedHeight(40)
        self.keys_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.keys_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.keys_table.itemSelectionChanged.connect(self._update_revoke_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshSecurityButton")
        self.refresh_button.setIcon(app_icon("refresh"))
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.add_key_button = QPushButton("Add backup USB key")
        self.add_key_button.setObjectName("addSecurityKeyButton")
        self.add_key_button.setIcon(app_icon("key"))
        self.add_key_button.clicked.connect(self._choose_new_keyfile)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(SPACE_2)
        actions.addWidget(self.add_key_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch()

        danger_zone = QFrame()
        danger_zone.setObjectName("dangerSection")
        danger_label = QLabel("Revoke a backup key")
        danger_label.setObjectName("sectionTitle")
        danger_help = QLabel(
            "The selected USB key will stop unlocking this vault. "
            "The connected key cannot be revoked."
        )
        danger_help.setObjectName("sectionDescription")
        danger_help.setWordWrap(True)
        self.revoke_key_button = QPushButton("Revoke selected key")
        self.revoke_key_button.setObjectName("revokeSecurityKeyButton")
        self.revoke_key_button.setIcon(app_icon("trash", "#f199a1"))
        self.revoke_key_button.setEnabled(False)
        self.revoke_key_button.clicked.connect(self._emit_revoke)
        danger_layout = QHBoxLayout(danger_zone)
        danger_layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        danger_copy = QVBoxLayout()
        danger_copy.addWidget(danger_label)
        danger_copy.addWidget(danger_help)
        danger_layout.addLayout(danger_copy, 1)
        danger_layout.addWidget(self.revoke_key_button)

        section.addWidget(self.key_count_label)
        section.addWidget(self.keys_table)
        section.addLayout(actions)
        section.addWidget(danger_zone)
        return section

    def _create_password_section(self) -> SectionCard:
        section = SectionCard(
            "Change password",
            "Choose a long, unique password. Your encrypted files and master key remain unchanged; "
            "only the registered unlock methods are updated.",
        )
        section.setMaximumWidth(720)

        self.current_password_edit = self._password_field(
            "securityCurrentPasswordEdit", "Current vault password"
        )
        self.new_password_edit = self._password_field(
            "securityNewPasswordEdit", "New vault password"
        )
        self.confirmation_edit = self._password_field(
            "securityConfirmPasswordEdit", "Repeat new password"
        )
        self.new_password_edit.textChanged.connect(self._update_password_strength)

        self.password_strength_label = QLabel("12+ characters recommended")
        self.password_strength_label.setObjectName("passwordStrength")
        self.show_passwords_checkbox = QCheckBox("Show passwords")
        self.show_passwords_checkbox.setObjectName("showSecurityPasswordsCheckbox")
        self.show_passwords_checkbox.toggled.connect(self._set_passwords_visible)

        password_form = QVBoxLayout()
        password_form.setContentsMargins(0, 0, 0, 0)
        password_form.setSpacing(SPACE_2)
        for label_text, field in (
            ("Current password", self.current_password_edit),
            ("New password", self.new_password_edit),
        ):
            label = QLabel(label_text)
            label.setObjectName("formLabel")
            password_form.addWidget(label)
            password_form.addWidget(field)
        password_form.addWidget(self.password_strength_label)
        confirmation_label = QLabel("Confirm new password")
        confirmation_label.setObjectName("formLabel")
        password_form.addWidget(confirmation_label)
        password_form.addWidget(self.confirmation_edit)
        password_form.addWidget(self.show_passwords_checkbox)

        self.additional_keys_widget = QWidget()
        additional_layout = QVBoxLayout(self.additional_keys_widget)
        additional_layout.setContentsMargins(0, 0, 0, 0)
        additional_layout.setSpacing(SPACE_2)
        self.additional_keys_label = QLabel()
        self.additional_keys_label.setObjectName("sectionDescription")
        self.additional_keys_label.setWordWrap(True)
        self.additional_keyfiles_list = QListWidget()
        self.additional_keyfiles_list.setObjectName("additionalPasswordKeyfilesList")
        self.additional_keyfiles_list.setMaximumHeight(112)
        add_existing_button = QPushButton("Select connected USB keys…")
        add_existing_button.setObjectName("selectPasswordKeyfilesButton")
        add_existing_button.setIcon(app_icon("folder"))
        add_existing_button.clicked.connect(self._choose_additional_keyfiles)
        remove_existing_button = QPushButton("Remove selection")
        remove_existing_button.setObjectName("removePasswordKeyfileButton")
        remove_existing_button.clicked.connect(self._remove_selected_keyfile)
        keyfile_buttons = QHBoxLayout()
        keyfile_buttons.addWidget(add_existing_button)
        keyfile_buttons.addWidget(remove_existing_button)
        keyfile_buttons.addStretch()
        additional_layout.addWidget(self.additional_keys_label)
        additional_layout.addWidget(self.additional_keyfiles_list)
        additional_layout.addLayout(keyfile_buttons)
        self.additional_keys_widget.hide()

        self.recovery_widget = QWidget()
        recovery_layout = QVBoxLayout(self.recovery_widget)
        recovery_layout.setContentsMargins(0, 0, 0, 0)
        recovery_layout.setSpacing(SPACE_2)
        self.recovery_code_label = QLabel("Offline recovery code")
        self.recovery_code_label.setObjectName("formLabel")
        recovery_help = QLabel(
            "Changing the password also updates recovery access. Paste the current code; "
            "it stays masked unless you explicitly reveal it."
        )
        recovery_help.setObjectName("formHelp")
        recovery_help.setWordWrap(True)
        self.recovery_code_edit = MaskedRecoveryCodeEdit()
        self.recovery_code_edit.setObjectName("securityRecoveryCodeEdit")
        self.recovery_code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.recovery_code_edit.setPlaceholderText("Paste the current UVR1 recovery code")
        self.show_recovery_checkbox = QCheckBox("Show recovery code")
        self.show_recovery_checkbox.toggled.connect(
            lambda visible: self.recovery_code_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
            )
        )
        recovery_layout.addWidget(self.recovery_code_label)
        recovery_layout.addWidget(recovery_help)
        recovery_layout.addWidget(self.recovery_code_edit)
        recovery_layout.addWidget(self.show_recovery_checkbox)

        self.change_password_button = QPushButton("Change password")
        self.change_password_button.setObjectName("changeSecurityPasswordButton")
        self.change_password_button.setIcon(app_icon("key", "#09201f"))
        self.change_password_button.clicked.connect(self._emit_password_change)

        section.addLayout(password_form)
        section.addWidget(self.additional_keys_widget)
        section.addWidget(self.recovery_widget)
        section.addWidget(self.change_password_button, 0, Qt.AlignmentFlag.AlignRight)
        return section

    def _password_field(self, object_name: str, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName(object_name)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(placeholder)
        field.setMaximumWidth(620)
        return field

    def _choose_new_keyfile(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Add backup USB key",
            "",
            "USB Vault keys (*.authkey);;All files (*)",
        )
        if selected_path:
            self.add_key_requested.emit(selected_path)

    def _emit_revoke(self) -> None:
        key_id_hex = self.selected_key_id_hex()
        if key_id_hex is not None:
            self.revoke_key_requested.emit(key_id_hex)

    def _choose_additional_keyfiles(self) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select every other registered USB key",
            "",
            "USB Vault keys (*.authkey);;All files (*)",
        )
        for selected_path in selected_paths:
            self.add_password_keyfile_path(selected_path)

    def _remove_selected_keyfile(self) -> None:
        selected_rows = sorted(
            {index.row() for index in self.additional_keyfiles_list.selectedIndexes()},
            reverse=True,
        )
        for row in selected_rows:
            self.additional_keyfiles_list.takeItem(row)

    def _emit_password_change(self) -> None:
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
            remaining = self._additional_keyfile_count - len(additional_paths)
            self.show_error(
                f"Connect and select {max(remaining, 0)} more registered USB key"
                f"{'s' if remaining != 1 else ''} before changing the password."
            )
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

    def _update_revoke_button(self) -> None:
        selected_rows = self.keys_table.selectionModel().selectedRows()
        if not selected_rows:
            self.revoke_key_button.setEnabled(False)
            return
        role_item = self.keys_table.item(selected_rows[0].row(), 1)
        is_current = role_item.data(Qt.ItemDataRole.UserRole) if role_item is not None else True
        self.revoke_key_button.setEnabled(is_current is False)

    def _set_passwords_visible(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.current_password_edit.setEchoMode(mode)
        self.new_password_edit.setEchoMode(mode)
        self.confirmation_edit.setEchoMode(mode)

    def _update_password_strength(self, password: str) -> None:
        length = len(password)
        if not password:
            text, level = "12+ characters recommended", ""
        elif length < 8:
            text, level = "Weak — make this password longer", "weak"
        elif length < 12:
            text, level = "Fair — 12+ characters is recommended", "medium"
        else:
            text, level = "Strong length", "strong"
        self.password_strength_label.setText(text)
        self.password_strength_label.setProperty("level", level)
        self.password_strength_label.style().unpolish(self.password_strength_label)
        self.password_strength_label.style().polish(self.password_strength_label)


def _short_key_id(key_id_hex: str) -> str:
    if len(key_id_hex) <= 14:
        return key_id_hex
    return f"{key_id_hex[:8]}…{key_id_hex[-6:]}"
