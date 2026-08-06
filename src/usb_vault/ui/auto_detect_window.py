"""Desktop window that automatically discovers mounted USB keys."""

from __future__ import annotations

from pathlib import Path

from usb_vault.core.errors import (
    VaultOperationError,
)
from usb_vault.platform.macos.usb_discovery import (
    MacOsUsbKeyLocator,
    UsbKeyLocator,
)
from usb_vault.ui.backend import (
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.background_backend import (
    BackgroundVaultBackend,
)
from usb_vault.ui.fully_async_window import (
    UnlockTaskResult,
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
from usb_vault.ui.usb_grace_window import (
    UsbGraceMainWindow,
)
from usb_vault.ui.workflow_secrets import (
    MutableTextSecret,
)

NO_MATCHING_USB_MESSAGE = (
    "No registered USB key was found. "
    "Insert a USB containing a root-level "
    ".authkey file and try again."
)


class AutoDetectUsbMainWindow(UsbGraceMainWindow):
    """Automatically select a registered key from mounted volumes."""

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
            rename_backend=(rename_backend),
        )

        self._key_locator = key_locator if key_locator is not None else MacOsUsbKeyLocator()

    def _on_unlock_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
        """Unlock with an explicit key or a detected mounted key."""
        if self.is_busy:
            self._show_busy_message()
            return

        password_secret = MutableTextSecret.from_text(password)
        self.unlock_page.clear_password()

        automatic_detection = not keyfile_path

        def operation() -> object:
            selected_keyfile_path: Path | None

            if keyfile_path:
                selected_keyfile_path = Path(keyfile_path)
            else:
                selected_keyfile_path = self._key_locator.find_matching_keyfile(Path(vault_path))

            if selected_keyfile_path is None:
                raise VaultOperationError(NO_MATCHING_USB_MESSAGE)

            candidate = UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=(selected_keyfile_path),
                password=(password_secret.text()),
            )

            try:
                entries = self._backend.unlock(candidate)
            except Exception:
                candidate.close()
                raise

            return UnlockTaskResult(
                vault=candidate,
                entries=entries,
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                UnlockTaskResult,
            ):
                self._show_protocol_error()
                return

            self.unlock_page.clear_error()
            self._activate_vault(
                value.vault,
                value.entries,
            )

            if automatic_detection:
                message = "Vault unlocked using the detected USB key."
            else:
                message = "Vault unlocked."

            self.statusBar().showMessage(
                message,
                5_000,
            )

        def failed(
            message: str,
        ) -> None:
            self.unlock_page.show_error(message)
            self.statusBar().showMessage(
                "Unlock failed.",
                5_000,
            )

        status_message = (
            "Searching mounted USB drives…" if automatic_detection else "Unlocking vault…"
        )

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=(status_message),
            secrets=(password_secret,),
        )
