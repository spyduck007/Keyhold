"""Final MVP window with automatic USB-triggered vault unlocking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import (
    QCloseEvent,
)

from usb_vault.platform.macos.usb_discovery import (
    MacOsUsbKeyLocator,
    UsbKeyLocator,
)
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
from usb_vault.ui.usb_unlock_waiter import (
    DEFAULT_USB_UNLOCK_POLL_INTERVAL_MS,
    UsbUnlockWaiter,
)
from usb_vault.ui.vault_cards_window import (
    VaultCardsMainWindow,
)
from usb_vault.ui.vault_library import (
    VaultLibraryStore,
)
from usb_vault.ui.workflow_secrets import (
    MutableTextSecret,
)


@dataclass(slots=True)
class PendingUsbUnlock:
    """Password and vault retained while waiting for the second factor."""

    vault_path: Path
    password: MutableTextSecret


class AutomaticUnlockMainWindow(VaultCardsMainWindow):
    """Wait for a registered USB and unlock once it appears."""

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
        unlock_poll_interval_ms: int = (DEFAULT_USB_UNLOCK_POLL_INTERVAL_MS),
    ) -> None:
        selected_locator: UsbKeyLocator = (
            key_locator if key_locator is not None else MacOsUsbKeyLocator()
        )

        self._pending_usb_unlock: PendingUsbUnlock | None = None
        self._unlock_waiter = UsbUnlockWaiter(
            locator=selected_locator,
            poll_interval_ms=(unlock_poll_interval_ms),
        )

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
            key_locator=(selected_locator),
            vault_library=(vault_library),
        )

        self._unlock_waiter.setParent(self)
        self._unlock_waiter.keyfile_found.connect(self._on_waiting_keyfile_found)
        self._unlock_waiter.scan_failed.connect(self._on_waiting_scan_failed)

        self.unlock_page.cancel_requested.connect(self._on_unlock_cancel_requested)

    @property
    def is_waiting_for_usb(self) -> bool:
        """Return whether a password is pending a matching USB key."""
        return self._pending_usb_unlock is not None and self._unlock_waiter.is_active

    @property
    def unlock_waiter(
        self,
    ) -> UsbUnlockWaiter:
        """Expose the USB waiter for focused tests."""
        return self._unlock_waiter

    def show_library_page(self) -> None:
        """Cancel pending authentication before showing cards."""
        self._cancel_pending_usb_unlock(reset_page=True)
        super().show_library_page()

    def show_setup_page(self) -> None:
        """Cancel pending authentication before setup."""
        self._cancel_pending_usb_unlock(reset_page=True)
        super().show_setup_page()

    def show_recovery_page(self) -> None:
        """Cancel pending authentication before recovery."""
        self._cancel_pending_usb_unlock(reset_page=True)
        super().show_recovery_page()

    def lock_vault(self) -> None:
        """Clear any pending password before locking."""
        self._cancel_pending_usb_unlock(reset_page=True)
        super().lock_vault()

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Clear pending authentication before closing."""
        self._cancel_pending_usb_unlock(reset_page=True)
        super().closeEvent(event)

    def _show_unlock_form(
        self,
        vault_path: Path,
        *,
        display_name: str,
    ) -> None:
        self._cancel_pending_usb_unlock(reset_page=True)
        super()._show_unlock_form(
            vault_path,
            display_name=display_name,
        )

    def _on_unlock_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
        """Unlock manually or begin waiting for a mounted USB key."""
        if keyfile_path:
            self._cancel_pending_usb_unlock(reset_page=True)
            super()._on_unlock_requested(
                vault_path,
                keyfile_path,
                password,
            )
            return

        if self.is_busy:
            self._show_busy_message()
            return

        self._cancel_pending_usb_unlock(reset_page=False)

        try:
            password_secret = MutableTextSecret.from_text(password)
        except (
            TypeError,
            ValueError,
        ) as error:
            self.unlock_page.show_error(str(error))
            return

        selected_vault_path = Path(vault_path)

        self.unlock_page.clear_password()
        self.unlock_page.clear_error()
        self.unlock_page.begin_waiting_for_usb()

        self._pending_usb_unlock = PendingUsbUnlock(
            vault_path=(selected_vault_path),
            password=(password_secret),
        )

        self.statusBar().showMessage(
            (
                "Waiting for a registered "
                "USB key. Insert it now; "
                "the vault will unlock "
                "automatically."
            )
        )

        self._unlock_waiter.start(selected_vault_path)

    def _on_waiting_keyfile_found(
        self,
        value: object,
    ) -> None:
        if not isinstance(
            value,
            Path,
        ):
            self._on_waiting_scan_failed(("USB key detection returned an invalid result."))
            return

        pending = self._pending_usb_unlock

        if pending is None:
            return

        self._pending_usb_unlock = None
        self._unlock_waiter.cancel()
        self.unlock_page.begin_unlocking()

        try:
            password = pending.password.text()

            super()._on_unlock_requested(
                str(pending.vault_path),
                str(value),
                password,
            )
        finally:
            pending.password.close()

        if not self.is_busy and not self.is_unlocked:
            self.unlock_page.end_waiting()

    def _on_waiting_scan_failed(
        self,
        message: str,
    ) -> None:
        self._cancel_pending_usb_unlock(reset_page=True)

        self.unlock_page.show_error(message)
        self.statusBar().showMessage(
            "USB key detection failed.",
            8_000,
        )

    def _on_unlock_cancel_requested(
        self,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        self._cancel_pending_usb_unlock(reset_page=True)
        self.show_library_page()

    def _on_busy_changed(
        self,
        busy: bool,
    ) -> None:
        super()._on_busy_changed(busy)

        if (
            not busy
            and not self.is_unlocked
            and self._pending_usb_unlock is None
            and self.unlock_page.is_unlocking
        ):
            self.unlock_page.end_waiting()

    def _cancel_pending_usb_unlock(
        self,
        *,
        reset_page: bool,
    ) -> None:
        self._unlock_waiter.cancel()

        pending = self._pending_usb_unlock
        self._pending_usb_unlock = None

        if pending is not None:
            pending.password.close()

        if reset_page and hasattr(
            self,
            "unlock_page",
        ):
            self.unlock_page.end_waiting()
            self.unlock_page.clear_password()
