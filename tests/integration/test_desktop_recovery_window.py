"""Integration tests for the desktop recovery workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.errors import UnlockError
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.recovery_backend import (
    RecoveredVault,
)
from usb_vault.ui.recovery_window import (
    RecoveryMainWindow,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)

KEY_ID = b"K" * 16
RECOVERY_CODE = "UVR1-OLD-RECOVERY-CODE"
ROTATED_RECOVERY_CODE = "UVR1-NEW-RECOVERY-CODE"


@dataclass
class FakeKeyfileProbe:
    """Always expose one available replacement USB identity."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        del keyfile_path
        return KEY_ID


class FakeVaultBackend:
    """Minimal normal-vault backend."""

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        vault.password_bytes()
        return ()

    def list_entries(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        vault.password_bytes()
        return ()

    def add_file(
        self,
        vault: UnlockedVault,
        source_path: Path,
        stored_name: str | None = None,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        return VaultEntrySummary(
            name=(stored_name or source_path.name),
            size=1,
        )

    def extract_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        del destination_path
        del overwrite

        vault.password_bytes()
        return VaultEntrySummary(
            name=stored_name,
            size=1,
        )

    def delete_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        return VaultEntrySummary(
            name=stored_name,
            size=1,
        )


@dataclass
class FakeRecoveryBackend:
    """Controllable recovery backend."""

    error: Exception | None = None
    requests: list[
        tuple[
            Path,
            Path,
            str,
            str,
            bool,
        ]
    ] = field(default_factory=list)

    def recover_vault(
        self,
        *,
        vault_path: Path,
        new_keyfile_path: Path,
        password: str,
        recovery_code: str,
        replace_existing_keys: bool,
    ) -> RecoveredVault:
        self.requests.append(
            (
                vault_path,
                new_keyfile_path,
                password,
                recovery_code,
                replace_existing_keys,
            )
        )

        if self.error is not None:
            raise self.error

        return RecoveredVault(
            vault=UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=(new_keyfile_path),
                password=password,
            ),
            entries=(
                VaultEntrySummary(
                    name="notes.txt",
                    size=12,
                ),
            ),
            recovery_code=(ROTATED_RECOVERY_CODE),
            replaced_existing_keys=(replace_existing_keys),
        )


def _show_window(
    window: RecoveryMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _fill_recovery_page(
    window: RecoveryMainWindow,
    *,
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
]:
    vault_path = tmp_path / "Private.vault"
    keyfile_path = tmp_path / "new-usb.authkey"

    window.recovery_page.vault_path_edit.setText(str(vault_path))
    window.recovery_page.new_keyfile_path_edit.setText(str(keyfile_path))
    window.recovery_page.password_edit.setText("test password")
    window.recovery_page.confirmation_edit.setText("test password")
    window.recovery_page.recovery_code_edit.setPlainText(RECOVERY_CODE)

    return (
        vault_path,
        keyfile_path,
    )


def test_successful_recovery_opens_vault(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = FakeRecoveryBackend()
    presented_codes: list[str] = []

    def present_recovery_code(
        parent: QWidget,
        recovery_code: str,
    ) -> None:
        assert parent.objectName() == "mainWindow"
        presented_codes.append(recovery_code)

    guard = SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    window = RecoveryMainWindow(
        backend=FakeVaultBackend(),
        recovery_backend=backend,
        recovery_presenter=(present_recovery_code),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window.show_recovery_page()

    (
        vault_path,
        keyfile_path,
    ) = _fill_recovery_page(
        window,
        tmp_path=tmp_path,
    )

    QTest.mouseClick(
        window.recovery_page.recover_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert backend.requests == [
        (
            vault_path,
            keyfile_path,
            "test password",
            RECOVERY_CODE,
            True,
        ),
    ]
    assert presented_codes == [
        ROTATED_RECOVERY_CODE,
    ]
    assert window.is_unlocked
    assert window.current_page_name == "vault"
    assert window.vault_page.table.rowCount() == 1
    assert guard.is_active
    assert window.unlock_page.keyfile_path_edit.text() == str(keyfile_path)
    assert window.recovery_page.recovery_code_edit.toPlainText() == ""


def test_failed_recovery_remains_on_recovery_page(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = FakeRecoveryBackend(error=UnlockError())
    guard = SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    window = RecoveryMainWindow(
        backend=FakeVaultBackend(),
        recovery_backend=backend,
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window.show_recovery_page()
    _fill_recovery_page(
        window,
        tmp_path=tmp_path,
    )

    QTest.mouseClick(
        window.recovery_page.recover_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert not window.is_unlocked
    assert window.current_page_name == "recovery"
    assert window.recovery_page.error_label.text() == "Unable to unlock vault."
    assert not guard.is_active
