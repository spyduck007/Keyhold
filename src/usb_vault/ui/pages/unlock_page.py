"""Compact two-step authentication screen for an existing vault."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from usb_vault.platform.macos.usb_volumes import UsbVolumeLocator
from usb_vault.ui.components import (
    AUTH_PANEL_MAX_WIDTH,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
    PageHeader,
    ResponsivePage,
    ScanningBar,
    StatusBadge,
)
from usb_vault.ui.icons import app_icon
from usb_vault.ui.usb_key_animation import UsbKeyAnimation
from usb_vault.ui.usb_volume_selector import UsbVolumeSelector


class UnlockPage(ResponsivePage):
    """Collect password first, then wait for a registered USB key."""

    unlock_requested = Signal(str, str, str)
    cancel_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        usb_volume_locator: UsbVolumeLocator | None = None,
    ) -> None:
        super().__init__(
            "unlockPage",
            max_width=AUTH_PANEL_MAX_WIDTH,
            parent=parent,
        )

        self._waiting_for_usb = False
        self._unlocking = False
        self._selected_vault_name: str | None = None

        self.header = PageHeader(
            "SECURE ACCESS",
            "Unlock a vault",
            "Enter your password first. You'll be asked for your registered USB key next.",
        )
        self.eyebrow = self.header.eyebrow_label
        self.title = self.header.title_label
        self.subtitle = self.header.description_label

        self.password_step = QLabel("1  Password")
        self.password_step.setObjectName("authStepActive")
        self.usb_step = QLabel("2  USB key")
        self.usb_step.setObjectName("authStepPending")
        steps = QHBoxLayout()
        steps.setContentsMargins(0, 0, 0, 0)
        steps.setSpacing(SPACE_2)
        steps.addWidget(self.password_step)
        steps.addWidget(self.usb_step)
        steps.addStretch()

        self.selected_vault_label = StatusBadge("Password required", tone="warning")
        self.selected_vault_label.setObjectName("selectedVaultLabel")
        self.selected_vault_label.hide()

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setObjectName("vaultPathEdit")
        self.vault_path_edit.setPlaceholderText("Select a .vault file")
        self.keyfile_path_edit = QLineEdit(self)
        self.keyfile_path_edit.setObjectName("keyfilePathEdit")
        self.keyfile_path_edit.setReadOnly(True)
        self.keyfile_path_edit.hide()
        self.keyfile_path_edit.setPlaceholderText("Optional mounted USB key")
        self.keyfile_path_edit.setToolTip(
            "Leave blank to wait automatically for a registered mounted USB key."
        )
        self.usb_volume_selector = UsbVolumeSelector(
            usb_volume_locator=usb_volume_locator,
            placeholder="Automatic detection, or select a USB",
        )
        self.usb_volume_combo = self.usb_volume_selector.combo
        self.usb_volume_combo.setObjectName("unlockUsbVolumeComboBox")
        self.usb_volume_selector.refresh_button.setObjectName("refreshUnlockUsbVolumesButton")
        self.usb_volume_selector.keyfile_path_changed.connect(self.keyfile_path_edit.setText)
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
        self.keyfile_browse_button = self.usb_volume_selector.refresh_button

        self.vault_selection_row = self._field_with_button(
            "Vault file",
            self.vault_path_edit,
            self.vault_browse_button,
        )
        self.manual_keyfile_row = self._labeled_widget(
            "USB key (optional)",
            self.usb_volume_selector,
        )

        password_label = QLabel("Vault password")
        password_label.setObjectName("formLabel")

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
        self.unlock_button.setIcon(app_icon("arrow_right", "#181818"))
        self.unlock_button.setIconSize(QSize(18, 18))
        self.unlock_button.setDefault(True)
        self.unlock_button.clicked.connect(self._emit_unlock)
        self.password_edit.returnPressed.connect(self._emit_unlock)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.unlock_button)

        self.form_surface = QWidget()
        form_layout = QVBoxLayout(self.form_surface)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(SPACE_3)
        form_layout.addWidget(self.selected_vault_label, 0, Qt.AlignmentFlag.AlignLeft)
        form_layout.addWidget(self.vault_selection_row)
        form_layout.addWidget(self.manual_keyfile_row)
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_edit)
        form_layout.addWidget(
            self.show_password_checkbox,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        form_layout.addWidget(self.error_label)
        form_layout.addSpacing(SPACE_2)
        form_layout.addLayout(actions)

        self.wait_surface = QWidget()
        self.wait_surface.hide()
        self.wait_surface.setMinimumHeight(360)
        self.wait_animation = UsbKeyAnimation()
        self.wait_animation.setMinimumSize(150, 130)
        self.waiting_heading = QLabel("Waiting for your USB key")
        self.waiting_heading.setObjectName("sectionTitle")
        self.waiting_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_detail = QLabel(
            "Insert a registered USB key. Unrelated devices are ignored automatically."
        )
        self.waiting_detail.setObjectName("keyWaitDetail")
        self.waiting_detail.setWordWrap(True)
        self.waiting_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_label = QLabel("Scanning for registered USB keys…")
        self.waiting_label.setObjectName("usbUnlockWaitingLabel")
        self.waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_label.setWordWrap(True)
        self.wait_progress = ScanningBar()
        self.detection_badge = StatusBadge("Scanning connected drives", tone="warning")
        self.detection_badge.hide()
        self.wait_cancel_button = QPushButton("Cancel")
        self.wait_cancel_button.setObjectName("cancelWaitingUnlockButton")
        self.wait_cancel_button.clicked.connect(self.cancel_requested.emit)

        wait_layout = QVBoxLayout(self.wait_surface)
        wait_layout.setContentsMargins(0, SPACE_3, 0, 0)
        wait_layout.setSpacing(SPACE_3)
        wait_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wait_layout.addWidget(self.wait_animation, 0, Qt.AlignmentFlag.AlignCenter)
        wait_layout.addWidget(self.waiting_heading)
        wait_layout.addWidget(self.waiting_detail)
        wait_layout.addWidget(self.waiting_label)
        wait_layout.addWidget(self.detection_badge, 0, Qt.AlignmentFlag.AlignCenter)
        wait_layout.addWidget(self.wait_progress, 0, Qt.AlignmentFlag.AlignCenter)
        wait_layout.addSpacing(SPACE_2)
        wait_layout.addWidget(self.wait_cancel_button, 0, Qt.AlignmentFlag.AlignCenter)

        self.auth_panel = QFrame()
        self.auth_panel.setObjectName("authPanel")
        panel_layout = QVBoxLayout(self.auth_panel)
        panel_layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        panel_layout.setSpacing(SPACE_4)
        panel_layout.addWidget(self.header)
        panel_layout.addLayout(steps)
        panel_layout.addWidget(self.form_surface)
        panel_layout.addWidget(self.wait_surface)

        self.content_layout.addWidget(self.auth_panel)
        self.content_layout.addStretch(1)
        self._update_keyfile_path()

    @property
    def is_waiting_for_usb(self) -> bool:
        return self._waiting_for_usb

    @property
    def is_unlocking(self) -> bool:
        return self._unlocking

    def set_selected_vault(self, display_name: str) -> None:
        self._selected_vault_name = display_name.strip() or "vault"
        self.header.set_title(f"Unlock {self._selected_vault_name}")
        self.header.set_description(
            "Enter the vault password. You'll be asked for your registered USB key next."
        )
        self.selected_vault_label.set_status("Registered USB key required next", "warning")
        self.selected_vault_label.show()
        self.vault_selection_row.hide()
        self.manual_keyfile_row.hide()

    def clear_selected_vault(self) -> None:
        self._selected_vault_name = None
        self.header.set_title("Unlock a vault")
        self.header.set_description(
            "Enter your password first. You'll be asked for your registered USB key next."
        )
        self.selected_vault_label.hide()
        self.vault_selection_row.show()
        self.manual_keyfile_row.show()

    def begin_waiting_for_usb(self) -> None:
        self._waiting_for_usb = True
        self._unlocking = False
        self._set_form_enabled(False)
        self.form_surface.hide()
        self.wait_surface.show()
        self.password_step.setObjectName("authStepPending")
        self.usb_step.setObjectName("authStepActive")
        self._repolish_steps()
        self.waiting_heading.setText("Waiting for your USB key")
        self.waiting_detail.setText(
            "Insert a registered USB key. Unrelated devices are ignored automatically."
        )
        self.waiting_label.setText("Scanning for registered USB keys…")
        self.waiting_label.show()
        self.detection_badge.hide()
        self.wait_progress.show()
        self.wait_animation.start()
        self.wait_progress.start()
        self.unlock_button.setText("Waiting for USB…")
        self.unlock_button.setEnabled(False)
        self.cancel_button.setText("Cancel")
        self.cancel_button.setEnabled(True)
        self.wait_cancel_button.setEnabled(True)

    def begin_unlocking(self) -> None:
        self._waiting_for_usb = False
        self._unlocking = True
        self._set_form_enabled(False)
        self.form_surface.hide()
        self.wait_surface.show()
        self.wait_cancel_button.setEnabled(False)
        self.wait_animation.stop()
        self.wait_progress.stop()
        self.wait_progress.hide()
        self.waiting_heading.setText("USB key detected")
        self.waiting_detail.setText("Validating registration and opening the encrypted vault…")
        self.waiting_label.hide()
        self.detection_badge.set_status("Registered key detected", "success")
        self.detection_badge.show()
        self.unlock_button.setText("Unlocking…")
        self.unlock_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def end_waiting(self) -> None:
        self._waiting_for_usb = False
        self._unlocking = False
        self._set_form_enabled(True)
        self.wait_animation.stop()
        self.wait_progress.stop()
        self.wait_surface.hide()
        self.form_surface.show()
        self.password_step.setObjectName("authStepActive")
        self.usb_step.setObjectName("authStepPending")
        self._repolish_steps()
        self.waiting_label.clear()
        self.waiting_label.hide()
        self.detection_badge.hide()
        self.waiting_heading.setText("Waiting for your USB key")
        self.waiting_detail.setText(
            "Insert a registered USB key. Unrelated devices are ignored automatically."
        )
        self.unlock_button.setText("Continue")
        self.unlock_button.setEnabled(True)
        self.cancel_button.setText("Back to vaults")
        self.cancel_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        self.password_edit.setProperty("error", True)
        self.password_edit.style().unpolish(self.password_edit)
        self.password_edit.style().polish(self.password_edit)

    def clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()
        self.password_edit.setProperty("error", False)
        self.password_edit.style().unpolish(self.password_edit)
        self.password_edit.style().polish(self.password_edit)

    def clear_password(self) -> None:
        self.password_edit.clear()
        self.show_password_checkbox.setChecked(False)

    def reset_after_lock(self) -> None:
        self.end_waiting()
        self.clear_password()
        self.clear_error()
        self.password_edit.setFocus()

    def _field_with_button(
        self,
        label_text: str,
        field: QLineEdit,
        button: QPushButton,
    ) -> QWidget:
        container = QWidget()
        label = QLabel(label_text)
        label.setObjectName("formLabel")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE_2)
        row.addWidget(field, 1)
        row.addWidget(button)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)
        layout.addWidget(label)
        layout.addLayout(row)
        return container

    def _labeled_widget(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        label = QLabel(label_text)
        label.setObjectName("formLabel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)
        layout.addWidget(label)
        layout.addWidget(widget)
        return container

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
        self.unlock_requested.emit(vault_path, keyfile_path, password)

    def _browse_vault(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self, "Open encrypted vault", "", "Keyhold vaults (*.vault);;All files (*)"
        )
        if selected_path:
            self.vault_path_edit.setText(selected_path)

    def refresh_usb_volumes(self) -> None:
        """Reload mounted USB devices available for manual selection."""
        self.usb_volume_selector.refresh_volumes()

    def _update_keyfile_path(self) -> None:
        keyfile_path = self.usb_volume_selector.keyfile_path
        self.keyfile_path_edit.setText(str(keyfile_path) if keyfile_path is not None else "")

    def _set_password_visible(self, visible: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    def _set_form_enabled(self, enabled: bool) -> None:
        for widget in (
            self.vault_path_edit,
            self.keyfile_path_edit,
            self.usb_volume_selector,
            self.password_edit,
            self.show_password_checkbox,
            self.vault_browse_button,
        ):
            widget.setEnabled(enabled)

    def _repolish_steps(self) -> None:
        for step in (self.password_step, self.usb_step):
            step.style().unpolish(step)
            step.style().polish(step)
