"""Fully asynchronous desktop window with file renaming."""

from __future__ import annotations

from collections.abc import (
    Sequence,
)

from PySide6.QtGui import (
    QAction,
)
from PySide6.QtWidgets import (
    QInputDialog,
    QLineEdit,
)

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.background_backend import (
    BackgroundVaultBackend,
    BackgroundVaultCredentials,
)
from usb_vault.ui.fully_async_window import (
    FullyAsyncSecurityMainWindow,
)
from usb_vault.ui.main_window import (
    RecoveryPresenter,
)
from usb_vault.ui.recovery_backend import (
    VaultRecoveryBackend,
)
from usb_vault.ui.rename_backend import (
    CoreRenameVaultBackend,
    RenameFileResult,
    RenameVaultBackend,
)
from usb_vault.ui.security_backend import (
    VaultSecurityBackend,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)
from usb_vault.ui.task_runner import (
    TaskRunner,
)


class RenameMainWindow(FullyAsyncSecurityMainWindow):
    """Add asynchronous metadata-only file renaming."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (SessionGuard | None) = None,
        recovery_backend: (VaultRecoveryBackend | None) = None,
        security_backend: (VaultSecurityBackend | None) = None,
        background_backend: (BackgroundVaultBackend | None) = None,
        task_runner: (TaskRunner | None) = None,
        rename_backend: (RenameVaultBackend | None) = None,
    ) -> None:
        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=session_guard,
            recovery_backend=(recovery_backend),
            security_backend=(security_backend),
            background_backend=(background_backend),
            task_runner=task_runner,
        )

        self._rename_backend = (
            rename_backend if rename_backend is not None else CoreRenameVaultBackend()
        )

        self.rename_action = QAction(
            "Rename Selected…",
            self,
        )
        self.rename_action.setObjectName("renameEntryAction")
        self.rename_action.setShortcut("F2")
        self.rename_action.setEnabled(False)
        self.rename_action.triggered.connect(self._on_rename_requested)

        entry_menu = self.menuBar().addMenu("&Entry")
        entry_menu.addAction(self.rename_action)

        self.vault_page.table.itemSelectionChanged.connect(self._update_rename_action)

        self._update_rename_action()

    def start_rename_entry(
        self,
        stored_name: str,
        new_name: str,
    ) -> bool:
        """Begin a metadata-only rename in the background."""
        if self.is_busy:
            self._show_busy_message()
            return False

        active_vault = self._require_vault()
        credentials = BackgroundVaultCredentials.from_unlocked(active_vault)

        def operation() -> object:
            return self._rename_backend.rename_file(
                credentials,
                stored_name,
                new_name,
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                RenameFileResult,
            ):
                self._show_task_protocol_error(active_vault)
                return

            if not self._is_current_vault(active_vault):
                return

            self.vault_page.set_entries(value.entries)
            self.statusBar().showMessage(
                (f"Renamed {stored_name} to {value.renamed.name}."),
                8_000,
            )

        return self._start_vault_task(
            active_vault=active_vault,
            credentials=credentials,
            operation=operation,
            succeeded=succeeded,
            status_message=(f"Renaming {stored_name}…"),
        )

    def lock_vault(self) -> None:
        """Disable rename while returning to the locked screen."""
        if hasattr(
            self,
            "rename_action",
        ):
            self.rename_action.setEnabled(False)

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
            "rename_action",
        ):
            self._update_rename_action()

    def _on_busy_changed(
        self,
        busy: bool,
    ) -> None:
        super()._on_busy_changed(busy)

        if hasattr(
            self,
            "rename_action",
        ):
            self._update_rename_action()

    def _on_rename_requested(
        self,
    ) -> None:
        stored_name = self.vault_page.selected_name()

        if stored_name is None:
            self.statusBar().showMessage(
                "Select a file to rename.",
                5_000,
            )
            return

        new_name, accepted = QInputDialog.getText(
            self,
            "Rename encrypted file",
            "New filename:",
            QLineEdit.EchoMode.Normal,
            stored_name,
        )

        if not accepted:
            return

        self.start_rename_entry(
            stored_name,
            new_name,
        )

    def _update_rename_action(
        self,
    ) -> None:
        self.rename_action.setEnabled(
            (
                self.is_unlocked
                and not self.is_busy
                and (self.vault_page.selected_name() is not None)
            )
        )
