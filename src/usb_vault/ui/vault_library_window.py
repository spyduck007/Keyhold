"""Desktop window that records successfully opened vaults."""

from __future__ import annotations

from collections.abc import (
    Sequence,
)

from PySide6.QtCore import (
    QTimer,
)

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.platform.macos.usb_discovery import (
    UsbKeyLocator,
)
from usb_vault.ui.auto_detect_window import (
    AutoDetectUsbMainWindow,
)
from usb_vault.ui.backend import (
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.background_backend import (
    BackgroundVaultBackend,
)
from usb_vault.ui.main_window import (
    RecoveryPresenter,
)
from usb_vault.ui.recovery_backend import (
    VaultRecoveryBackend,
)
from usb_vault.ui.rename_backend import (
    RenameVaultBackend,
)
from usb_vault.ui.security_backend import (
    VaultSecurityBackend,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)
from usb_vault.ui.task_runner import (
    TaskRunner,
)
from usb_vault.ui.usb_grace import (
    UsbGraceSessionGuard,
)
from usb_vault.ui.vault_library import (
    VaultLibraryError,
    VaultLibraryStore,
)


class VaultLibraryMainWindow(AutoDetectUsbMainWindow):
    """Persist every successfully activated vault."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (UsbGraceSessionGuard | None) = None,
        recovery_backend: (VaultRecoveryBackend | None) = None,
        security_backend: (VaultSecurityBackend | None) = None,
        background_backend: (BackgroundVaultBackend | None) = None,
        task_runner: (TaskRunner | None) = None,
        rename_backend: (RenameVaultBackend | None) = None,
        key_locator: (UsbKeyLocator | None) = None,
        vault_library: (VaultLibraryStore | None) = None,
    ) -> None:
        self._vault_library = vault_library if vault_library is not None else VaultLibraryStore()
        self._last_library_error: str | None = None

        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=session_guard,
            recovery_backend=(recovery_backend),
            security_backend=(security_backend),
            background_backend=(background_backend),
            task_runner=task_runner,
            rename_backend=(rename_backend),
            key_locator=key_locator,
        )

    @property
    def vault_library(
        self,
    ) -> VaultLibraryStore:
        """Return the persistent registry used by this window."""
        return self._vault_library

    @property
    def last_library_error(
        self,
    ) -> str | None:
        """Return the most recent non-fatal registry failure."""
        return self._last_library_error

    def _activate_vault(
        self,
        vault: UnlockedVault,
        entries: Sequence[VaultEntrySummary],
    ) -> None:
        super()._activate_vault(
            vault,
            entries,
        )

        try:
            self._vault_library.register_vault(vault.vault_path)
        except (
            OSError,
            ValueError,
            VaultError,
            VaultLibraryError,
        ) as error:
            message = str(error).strip()

            if not message:
                message = "Unable to update the vault library."

            self._last_library_error = message
            QTimer.singleShot(
                0,
                lambda: self._show_library_warning(message),
            )
        else:
            self._last_library_error = None

    def _show_library_warning(
        self,
        message: str,
    ) -> None:
        if not self.is_unlocked:
            return

        self.statusBar().showMessage(
            (f"Vault opened, but its library entry could not be updated: {message}"),
            10_000,
        )
