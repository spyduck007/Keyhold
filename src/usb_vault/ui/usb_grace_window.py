"""Desktop window with a USB-key reconnection grace period."""

from __future__ import annotations

from usb_vault.ui.backend import (
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
from usb_vault.ui.rename_window import (
    RenameMainWindow,
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


class UsbGraceMainWindow(RenameMainWindow):
    """Keep a vault open briefly while the same USB key returns."""

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
    ) -> None:
        selected_guard = session_guard if session_guard is not None else UsbGraceSessionGuard()

        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=(selected_guard),
            recovery_backend=(recovery_backend),
            security_backend=(security_backend),
            background_backend=(background_backend),
            task_runner=task_runner,
            rename_backend=(rename_backend),
        )

        self._usb_grace_session_guard = selected_guard

        if selected_guard.parent() is None:
            selected_guard.setParent(self)

        selected_guard.usb_key_grace_started.connect(self._show_usb_grace_warning)
        selected_guard.usb_key_restored.connect(self._show_usb_restored)

    @property
    def usb_grace_session_guard(
        self,
    ) -> UsbGraceSessionGuard:
        """Return the production USB grace-period monitor."""
        return self._usb_grace_session_guard

    def _show_usb_grace_warning(
        self,
        grace_period_ms: int,
    ) -> None:
        seconds = _display_seconds(grace_period_ms)

        self.statusBar().showMessage(
            (
                "USB key unavailable. Reinsert "
                "the same key within "
                f"{seconds} second(s) to keep "
                "the vault unlocked."
            )
        )

    def _show_usb_restored(self) -> None:
        if not self.is_unlocked:
            return

        self.statusBar().showMessage(
            ("USB key restored. Vault remains unlocked."),
            5_000,
        )

    def _lock_after_usb_loss(self) -> None:
        self._lock_with_message(
            ("USB key remained unavailable after the reconnection period. Vault locked.")
        )


def _display_seconds(
    milliseconds: int,
) -> int:
    return max(
        1,
        (milliseconds + 999) // 1_000,
    )
