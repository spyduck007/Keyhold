"""Monitored desktop window with an integrated recovery workflow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction

from usb_vault.core.errors import VaultError
from usb_vault.ui.backend import VaultBackend
from usb_vault.ui.main_window import (
    RecoveryPresenter,
)
from usb_vault.ui.monitored_window import (
    MonitoredMainWindow,
)
from usb_vault.ui.pages.recovery_page import (
    RecoveryPage,
)
from usb_vault.ui.recovery_backend import (
    CoreVaultRecoveryBackend,
    VaultRecoveryBackend,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)


class RecoveryMainWindow(MonitoredMainWindow):
    """Add password-plus-recovery-code USB restoration."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (SessionGuard | None) = None,
        recovery_backend: (VaultRecoveryBackend | None) = None,
    ) -> None:
        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=session_guard,
        )

        self._vault_recovery_backend = (
            recovery_backend if recovery_backend is not None else CoreVaultRecoveryBackend()
        )

        self.recovery_page = RecoveryPage()
        self._pages.addWidget(self.recovery_page)

        self.recovery_page.recovery_requested.connect(self._on_recovery_requested)
        self.recovery_page.cancel_requested.connect(self._show_unlock_page)

        self.recover_access_action = QAction(
            "Recover Access…",
            self,
        )
        self.recover_access_action.setObjectName("recoverAccessAction")
        self.recover_access_action.triggered.connect(self.show_recovery_page)

        recovery_menu = self.menuBar().addMenu("&Recovery")
        recovery_menu.addAction(self.recover_access_action)

    @property
    def current_page_name(self) -> str:
        """Return the current desktop workflow page."""
        if self._pages.currentWidget() is self.recovery_page:
            return "recovery"

        return super().current_page_name

    def show_recovery_page(self) -> None:
        """Open a clean USB-recovery form."""
        prefilled_vault_path = self.unlock_page.vault_path_edit.text().strip()

        if self.is_unlocked:
            self.lock_vault()

        self.recovery_page.reset()

        if prefilled_vault_path:
            self.recovery_page.vault_path_edit.setText(prefilled_vault_path)

        self._pages.setCurrentWidget(self.recovery_page)
        self.statusBar().showMessage(
            ("Recover access using the vault password and recovery code."),
            8_000,
        )

    def _on_recovery_requested(
        self,
        vault_path: str,
        new_keyfile_path: str,
        password: str,
        recovery_code: str,
        replace_existing_keys: bool,
    ) -> None:
        try:
            recovered = self._vault_recovery_backend.recover_vault(
                vault_path=Path(vault_path),
                new_keyfile_path=Path(new_keyfile_path),
                password=password,
                recovery_code=(recovery_code),
                replace_existing_keys=(replace_existing_keys),
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self.recovery_page.clear_sensitive_fields()
            self.recovery_page.show_error(str(error))
            self.statusBar().showMessage(
                "Vault recovery failed.",
                8_000,
            )
            return

        self.recovery_page.clear_sensitive_fields()

        self.unlock_page.vault_path_edit.setText(str(recovered.vault.vault_path))
        self.unlock_page.keyfile_path_edit.setText(str(recovered.vault.keyfile_path))

        self._recovery_presenter(
            self,
            recovered.recovery_code,
        )
        self._activate_vault(
            recovered.vault,
            recovered.entries,
        )

        if recovered.replaced_existing_keys:
            detail = "Previous USB keys were revoked."
        else:
            detail = "Previous USB keys were preserved."

        self.statusBar().showMessage(
            (f"USB access recovered. {detail}"),
            10_000,
        )
