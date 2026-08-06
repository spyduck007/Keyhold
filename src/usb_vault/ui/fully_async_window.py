"""Desktop window with every expensive workflow off the GUI thread."""

from __future__ import annotations

from collections.abc import (
    Sequence,
)
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QMessageBox,
)

from usb_vault.core.vault.key_management import (
    UsbKeySummary,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.async_window import (
    AsyncSecurityMainWindow,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.recovery_backend import (
    RecoveredVault,
)
from usb_vault.ui.security_backend import (
    PasswordUpdatedVault,
    SecuritySnapshot,
)
from usb_vault.ui.setup_backend import (
    CreatedVault,
)
from usb_vault.ui.task_runner import (
    TaskFailureHandler,
    TaskFunction,
    TaskSuccessHandler,
)
from usb_vault.ui.workflow_secrets import (
    MutableTextSecret,
)


@dataclass(frozen=True, slots=True)
class UnlockTaskResult:
    """An authenticated UI session returned by a worker."""

    vault: UnlockedVault
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]


@dataclass(frozen=True, slots=True)
class SecurityKeyChangeResult:
    """A USB-key mutation and its best-effort refreshed snapshot."""

    key: UsbKeySummary
    snapshot: SecuritySnapshot | None
    refresh_error: str | None


class FullyAsyncSecurityMainWindow(AsyncSecurityMainWindow):
    """Run credential and file workflows outside the GUI thread."""

    def show_setup_page(self) -> None:
        """Open setup only while no operation is active."""
        if self.is_busy:
            self._show_busy_message()
            return

        super().show_setup_page()

    def show_recovery_page(self) -> None:
        """Open recovery only while no operation is active."""
        if self.is_busy:
            self._show_busy_message()
            return

        super().show_recovery_page()

    def show_security_page(self) -> None:
        """Open Security Center and load its metadata asynchronously."""
        if self.is_busy:
            self._show_busy_message()
            return

        if not self.is_unlocked:
            self.statusBar().showMessage(
                ("Unlock a vault before opening the Security Center."),
                8_000,
            )
            return

        self.security_page.clear_sensitive_fields()
        self.security_page.clear_error()
        self._pages.setCurrentWidget(self.security_page)

        self._start_security_snapshot(status_message=("Loading vault security settings…"))

    def _on_unlock_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        self._usb_ejector.record_keyfile_path(Path(keyfile_path))
        password_secret = MutableTextSecret.from_text(password)
        self.unlock_page.clear_password()

        def operation() -> object:
            candidate = UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=(keyfile_path),
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
            self.statusBar().showMessage(
                "Vault unlocked.",
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

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=("Unlocking vault…"),
            secrets=(password_secret,),
        )

    def _on_setup_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        self._usb_ejector.record_keyfile_path(Path(keyfile_path))
        password_secret = MutableTextSecret.from_text(password)
        self.setup_page.clear_sensitive_fields()

        def operation() -> object:
            return self._setup_backend.create_vault(
                vault_path=Path(vault_path),
                keyfile_path=Path(keyfile_path),
                password=(password_secret.text()),
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                CreatedVault,
            ):
                self._show_protocol_error()
                return

            self.setup_page.clear_error()

            self.unlock_page.vault_path_edit.setText(str(value.vault.vault_path))
            self.unlock_page.keyfile_path_edit.setText(str(value.vault.keyfile_path))

            self._recovery_presenter(
                self,
                value.recovery_code,
            )
            self._activate_vault(
                value.vault,
                value.entries,
            )

            self.statusBar().showMessage(
                "Vault created and unlocked.",
                8_000,
            )

        def failed(
            message: str,
        ) -> None:
            self.setup_page.show_error(message)
            self.statusBar().showMessage(
                "Vault creation failed.",
                8_000,
            )

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=("Creating encrypted vault…"),
            secrets=(password_secret,),
        )

    def _on_recovery_requested(
        self,
        vault_path: str,
        new_keyfile_path: str,
        password: str,
        recovery_code: str,
        replace_existing_keys: bool,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        self._usb_ejector.record_keyfile_path(Path(new_keyfile_path))
        password_secret = MutableTextSecret.from_text(password)
        recovery_secret = MutableTextSecret.from_text(recovery_code)
        self.recovery_page.clear_sensitive_fields()

        def operation() -> object:
            return self._vault_recovery_backend.recover_vault(
                vault_path=Path(vault_path),
                new_keyfile_path=Path(new_keyfile_path),
                password=(password_secret.text()),
                recovery_code=(recovery_secret.text()),
                replace_existing_keys=(replace_existing_keys),
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                RecoveredVault,
            ):
                self._show_protocol_error()
                return

            self.recovery_page.clear_error()

            self.unlock_page.vault_path_edit.setText(str(value.vault.vault_path))
            self.unlock_page.keyfile_path_edit.setText(str(value.vault.keyfile_path))

            self._recovery_presenter(
                self,
                value.recovery_code,
            )
            self._activate_vault(
                value.vault,
                value.entries,
            )

            detail = (
                "Previous USB keys were revoked."
                if value.replaced_existing_keys
                else ("Previous USB keys were preserved.")
            )

            self.statusBar().showMessage(
                (f"USB access recovered. {detail}"),
                10_000,
            )

        def failed(
            message: str,
        ) -> None:
            self.recovery_page.show_error(message)
            self.statusBar().showMessage(
                "Vault recovery failed.",
                8_000,
            )

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=("Recovering USB access…"),
            secrets=(
                password_secret,
                recovery_secret,
            ),
        )

    def _refresh_security_snapshot(
        self,
    ) -> bool:
        """Refresh Security Center metadata asynchronously."""
        if self.is_busy:
            self._show_busy_message()
            return False

        if not self.is_unlocked:
            return False

        return self._start_security_snapshot(status_message=("Refreshing vault security settings…"))

    def _start_security_snapshot(
        self,
        *,
        status_message: str,
    ) -> bool:
        active_vault = self._require_vault()

        try:
            task_vault = _copy_unlocked_vault(active_vault)
        except (
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            self.security_page.show_error(str(error))
            return False

        def operation() -> object:
            try:
                return self._security_backend.snapshot(task_vault)
            finally:
                task_vault.close()

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                SecuritySnapshot,
            ):
                self._show_protocol_error()
                return

            if not self._is_current_vault(active_vault):
                return

            self.security_page.set_snapshot(value)
            self.security_page.clear_error()
            self.statusBar().showMessage(
                ("Vault security settings loaded."),
                5_000,
            )

        def failed(
            message: str,
        ) -> None:
            if not self._is_current_vault(active_vault):
                return

            self.security_page.show_error(message)
            self.statusBar().showMessage(
                ("Unable to load security settings."),
                8_000,
            )

        return self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=(status_message),
        )

    def _on_add_key_requested(
        self,
        new_keyfile_path: str,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        self._usb_ejector.record_keyfile_path(Path(new_keyfile_path))
        active_vault = self._require_vault()
        task_vault = _copy_unlocked_vault(active_vault)

        def operation() -> object:
            try:
                key = self._security_backend.add_key(
                    task_vault,
                    Path(new_keyfile_path),
                )
                snapshot, refresh_error = self._best_effort_snapshot(task_vault)

                return SecurityKeyChangeResult(
                    key=key,
                    snapshot=snapshot,
                    refresh_error=(refresh_error),
                )
            finally:
                task_vault.close()

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                SecurityKeyChangeResult,
            ):
                self._show_protocol_error()
                return

            if not self._is_current_vault(active_vault):
                return

            self._apply_key_change_snapshot(value)
            self.statusBar().showMessage(
                (f"Backup USB created. Key ID: {value.key.key_id_hex}"),
                10_000,
            )

        def failed(
            message: str,
        ) -> None:
            if not self._is_current_vault(active_vault):
                return

            self.security_page.show_error(message)
            self.statusBar().showMessage(
                "Backup USB creation failed.",
                8_000,
            )

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=("Creating backup USB key…"),
        )

    def _on_revoke_key_requested(
        self,
        key_id_hex: str,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        answer = QMessageBox.question(
            self,
            "Revoke USB key?",
            (f"This USB key will no longer unlock the vault:\n\n{key_id_hex}"),
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        active_vault = self._require_vault()
        task_vault = _copy_unlocked_vault(active_vault)

        def operation() -> object:
            try:
                key = self._security_backend.revoke_key(
                    task_vault,
                    key_id_hex,
                )
                snapshot, refresh_error = self._best_effort_snapshot(task_vault)

                return SecurityKeyChangeResult(
                    key=key,
                    snapshot=snapshot,
                    refresh_error=(refresh_error),
                )
            finally:
                task_vault.close()

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                SecurityKeyChangeResult,
            ):
                self._show_protocol_error()
                return

            if not self._is_current_vault(active_vault):
                return

            self._apply_key_change_snapshot(value)
            self.statusBar().showMessage(
                (f"USB key revoked: {value.key.key_id_hex}"),
                10_000,
            )

        def failed(
            message: str,
        ) -> None:
            if not self._is_current_vault(active_vault):
                return

            self.security_page.show_error(message)
            self.statusBar().showMessage(
                "USB-key revocation failed.",
                8_000,
            )

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=("Revoking USB key…"),
        )

    def _on_password_change_requested(
        self,
        current_password: str,
        new_password: str,
        additional_keyfile_paths: object,
        recovery_code: str,
    ) -> None:
        if self.is_busy:
            self._show_busy_message()
            return

        try:
            paths = _path_sequence(additional_keyfile_paths)
        except (
            TypeError,
            ValueError,
        ) as error:
            self.security_page.show_error(str(error))
            return

        self._record_additional_usb_keyfiles(paths)
        active_vault = self._require_vault()
        task_vault = _copy_unlocked_vault(active_vault)

        current_secret = MutableTextSecret.from_text(current_password)
        new_secret = MutableTextSecret.from_text(new_password)
        recovery_secret = MutableTextSecret.from_text(
            recovery_code,
            allow_empty=True,
        )

        self.security_page.clear_sensitive_fields()

        def operation() -> object:
            try:
                return self._security_backend.change_password(
                    task_vault,
                    current_password=(current_secret.text()),
                    new_password=(new_secret.text()),
                    additional_keyfile_paths=(paths),
                    recovery_code=(recovery_secret.text()),
                )
            finally:
                task_vault.close()

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                PasswordUpdatedVault,
            ):
                self._show_protocol_error()
                return

            if not self._is_current_vault(active_vault):
                value.vault.close()
                return

            self.security_page.clear_error()
            self._activate_vault(
                value.vault,
                value.entries,
            )

            recovery_detail = " Recovery access was updated." if value.recovery_updated else ""

            self.statusBar().showMessage(
                (f"Password changed for {value.key_count} USB key(s).{recovery_detail}"),
                10_000,
            )

        def failed(
            message: str,
        ) -> None:
            if not self._is_current_vault(active_vault):
                return

            self.security_page.show_error(message)
            self.statusBar().showMessage(
                "Password change failed.",
                8_000,
            )

        self._start_workflow_task(
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            status_message=("Changing vault password…"),
            secrets=(
                current_secret,
                new_secret,
                recovery_secret,
            ),
        )

    def _best_effort_snapshot(
        self,
        task_vault: UnlockedVault,
    ) -> tuple[
        SecuritySnapshot | None,
        str | None,
    ]:
        try:
            return (
                self._security_backend.snapshot(task_vault),
                None,
            )
        except Exception as error:
            return (
                None,
                _error_message(error),
            )

    def _apply_key_change_snapshot(
        self,
        result: SecurityKeyChangeResult,
    ) -> None:
        if result.snapshot is not None:
            self.security_page.set_snapshot(result.snapshot)
            self.security_page.clear_error()
            return

        refresh_error_message = (
            "The USB-key change succeeded, "
            "but the settings could not be "
            "refreshed: "
            f"{result.refresh_error}"
        )
        self.security_page.show_error(refresh_error_message)

    def _start_workflow_task(
        self,
        *,
        operation: TaskFunction,
        succeeded: TaskSuccessHandler,
        failed: TaskFailureHandler,
        status_message: str,
        secrets: Sequence[MutableTextSecret] = (),
    ) -> bool:
        if self.is_busy:
            _close_secrets(secrets)
            self._show_busy_message()
            return False

        self._allow_manual_lock_during_task = False
        self.statusBar().showMessage(status_message)

        def guarded_operation() -> object:
            try:
                return operation()
            finally:
                _close_secrets(secrets)

        try:
            self._task_runner.start(
                guarded_operation,
                succeeded=succeeded,
                failed=failed,
            )
        except (
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            _close_secrets(secrets)
            self._allow_manual_lock_during_task = True
            self._show_status_error(str(error))
            return False

        return True

    def _on_busy_changed(
        self,
        busy: bool,
    ) -> None:
        super()._on_busy_changed(busy)

        allow_manual_lock = getattr(
            self,
            "_allow_manual_lock_during_task",
            True,
        )

        if busy and not allow_manual_lock:
            self.lock_action.setEnabled(False)

        if not busy:
            self._allow_manual_lock_during_task = True

    def _show_protocol_error(self) -> None:
        self._show_status_error("Background operation returned an invalid result.")


def _copy_unlocked_vault(
    vault: UnlockedVault,
) -> UnlockedVault:
    """Copy a UI session for use by one worker."""
    password_buffer = bytearray(vault.password_bytes())

    try:
        password = bytes(password_buffer).decode("utf-8")

        return UnlockedVault.create(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=password,
        )
    finally:
        for index in range(len(password_buffer)):
            password_buffer[index] = 0


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


def _close_secrets(
    secrets: Sequence[MutableTextSecret],
) -> None:
    for secret in secrets:
        secret.close()


def _error_message(
    error: Exception,
) -> str:
    message = str(error).strip()

    if message:
        return message

    return "Operation failed."
