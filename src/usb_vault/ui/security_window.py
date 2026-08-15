"""Desktop window with integrated vault security management."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMessageBox,
)

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.icons import app_icon
from usb_vault.ui.main_window import (
    RecoveryPresenter,
)
from usb_vault.ui.pages.security_page import (
    SecurityPage,
)
from usb_vault.ui.recovery_backend import (
    VaultRecoveryBackend,
)
from usb_vault.ui.recovery_window import (
    RecoveryMainWindow,
)
from usb_vault.ui.security_backend import (
    CoreVaultSecurityBackend,
    VaultSecurityBackend,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)


class SecurityMainWindow(RecoveryMainWindow):
    """Add USB-key and password management to the desktop app."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (SessionGuard | None) = None,
        recovery_backend: (VaultRecoveryBackend | None) = None,
        security_backend: (VaultSecurityBackend | None) = None,
    ) -> None:
        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=session_guard,
            recovery_backend=(recovery_backend),
        )

        self._security_backend = (
            security_backend if security_backend is not None else CoreVaultSecurityBackend()
        )

        self.security_page = SecurityPage()
        self._pages.addWidget(self.security_page)

        self.security_page.refresh_requested.connect(self._refresh_security_snapshot)
        self.security_page.add_key_requested.connect(self._on_add_key_requested)
        self.security_page.revoke_key_requested.connect(self._on_revoke_key_requested)
        self.security_page.password_change_requested.connect(self._on_password_change_requested)
        self.security_page.close_requested.connect(self._show_vault_page)

        self.security_action = QAction(
            "Vault Security…",
            self,
        )
        self.security_action.setObjectName("vaultSecurityAction")
        self.security_action.setIcon(app_icon("key"))
        self.security_action.setEnabled(False)
        self.security_action.triggered.connect(self.show_security_page)

        self.sidebar.add_item(
            "security",
            "Security",
            app_icon("key", "#c6c6c6"),
            self.security_action.trigger,
            group="access",
            enabled=False,
        )
        self._bind_sidebar_action("security", self.security_action)
        self._register_page_navigation(self.security_page, "security")

        security_menu = self.menuBar().addMenu("&Security")
        security_menu.addAction(self.security_action)

    @property
    def current_page_name(self) -> str:
        """Return the current desktop workflow page."""
        if self._pages.currentWidget() is self.security_page:
            return "security"

        return super().current_page_name

    def show_security_page(self) -> None:
        """Open the Security Center for the active vault."""
        if not self.is_unlocked:
            self.statusBar().showMessage(
                ("Unlock a vault before opening the Security Center."),
                8_000,
            )
            return

        self.security_page.clear_sensitive_fields()
        self.security_page.clear_error()
        self.security_page.set_vault_context(str(self._require_vault().vault_path))

        if not self._refresh_security_snapshot():
            return

        self._pages.setCurrentWidget(self.security_page)
        self.statusBar().showMessage(
            "Vault security settings opened.",
            5_000,
        )

    def lock_vault(self) -> None:
        """Disable security actions while locking."""
        if hasattr(
            self,
            "security_action",
        ):
            self.security_action.setEnabled(False)

        super().lock_vault()

    def _activate_vault(
        self,
        vault: UnlockedVault,
        entries: Sequence[VaultEntrySummary],
    ) -> None:
        super()._activate_vault(
            vault,
            entries,
        )

        if hasattr(
            self,
            "security_action",
        ):
            self.security_action.setEnabled(True)

    def _refresh_security_snapshot(
        self,
    ) -> bool:
        try:
            snapshot = self._security_backend.snapshot(self._require_vault())
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self.security_page.show_error(str(error))
            self.statusBar().showMessage(
                "Unable to load security settings.",
                8_000,
            )
            return False

        self.security_page.set_snapshot(snapshot)
        self.security_page.clear_error()
        return True

    def _on_add_key_requested(
        self,
        new_keyfile_path: str,
    ) -> None:
        try:
            result = self._security_backend.add_key(
                self._require_vault(),
                Path(new_keyfile_path),
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self.security_page.show_error(str(error))
            self.statusBar().showMessage(
                "Backup USB creation failed.",
                8_000,
            )
            return

        self._refresh_security_snapshot()
        self._record_additional_usb_keyfiles((Path(new_keyfile_path),))
        self.statusBar().showMessage(
            (f"Backup USB created. Key ID: {result.key_id_hex}"),
            10_000,
        )

    def _on_revoke_key_requested(
        self,
        key_id_hex: str,
    ) -> None:
        answer = QMessageBox.question(
            self,
            "Revoke USB key?",
            (f"This USB key will no longer unlock the vault:\n\n{key_id_hex}"),
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._security_backend.revoke_key(
                self._require_vault(),
                key_id_hex,
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self.security_page.show_error(str(error))
            self.statusBar().showMessage(
                "USB-key revocation failed.",
                8_000,
            )
            return

        self._refresh_security_snapshot()
        self.statusBar().showMessage(
            (f"USB key revoked: {result.key_id_hex}"),
            10_000,
        )

    def _on_password_change_requested(
        self,
        current_password: str,
        new_password: str,
        additional_keyfile_paths: object,
        recovery_code: str,
    ) -> None:
        try:
            paths = _path_sequence(additional_keyfile_paths)
            self._record_additional_usb_keyfiles(paths)
            updated = self._security_backend.change_password(
                self._require_vault(),
                current_password=(current_password),
                new_password=(new_password),
                additional_keyfile_paths=(paths),
                recovery_code=(recovery_code),
            )
        except (
            VaultError,
            OSError,
            TypeError,
            ValueError,
            RuntimeError,
        ) as error:
            self.security_page.clear_sensitive_fields()
            self.security_page.show_error(str(error))
            self.statusBar().showMessage(
                "Password change failed.",
                8_000,
            )
            return

        self.security_page.clear_sensitive_fields()
        self._activate_vault(
            updated.vault,
            updated.entries,
        )

        recovery_detail = " Recovery access was updated." if updated.recovery_updated else ""

        self.statusBar().showMessage(
            (f"Password changed for {updated.key_count} USB key(s).{recovery_detail}"),
            10_000,
        )

    def _show_vault_page(self) -> None:
        if not self.is_unlocked:
            self._show_unlock_page()
            return

        self._pages.setCurrentWidget(self.vault_page)


def _path_sequence(
    value: object,
) -> tuple[Path, ...]:
    if not isinstance(
        value,
        tuple,
    ):
        raise TypeError("additional keyfile paths must be a tuple")

    if not all(
        isinstance(
            item,
            str,
        )
        for item in value
    ):
        raise TypeError("every additional keyfile path must be a string")

    return tuple(Path(item) for item in value)
