"""Integration tests for fully asynchronous desktop workflows."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QTimer,
)
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.vault.key_management import (
    UsbKeySummary,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.fully_async_window import (
    FullyAsyncSecurityMainWindow,
)
from usb_vault.ui.recovery_backend import (
    RecoveredVault,
)
from usb_vault.ui.security_backend import (
    PasswordUpdatedVault,
    SecuritySnapshot,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)
from usb_vault.ui.setup_backend import (
    CreatedVault,
)

KEY_ID = b"K" * 16
BACKUP_KEY_ID = b"B" * 16


@dataclass
class FakeKeyfileProbe:
    """Keep a test USB identity available."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        del keyfile_path
        return KEY_ID


class ImmediateVaultBackend:
    """Minimal normal backend for workflow tests."""

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        vault.password_bytes()
        return (
            VaultEntrySummary(
                name="notes.txt",
                size=12,
            ),
        )

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


class BlockingUnlockBackend(ImmediateVaultBackend):
    """Block unlock until released by the test."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        vault.password_bytes()
        self.started.set()
        _wait_for_release(self.release)

        return super().unlock(vault)


class BlockingSetupBackend:
    """Block new-vault creation until released."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def create_vault(
        self,
        *,
        vault_path: Path,
        keyfile_path: Path,
        password: str,
    ) -> CreatedVault:
        self.started.set()
        _wait_for_release(self.release)

        return CreatedVault(
            vault=UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                password=password,
            ),
            entries=(),
            recovery_code=("UVR1-NEW-SETUP-CODE"),
        )


class BlockingRecoveryBackend:
    """Block recovery until released."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def recover_vault(
        self,
        *,
        vault_path: Path,
        new_keyfile_path: Path,
        password: str,
        recovery_code: str,
        replace_existing_keys: bool,
    ) -> RecoveredVault:
        assert recovery_code
        self.started.set()
        _wait_for_release(self.release)

        return RecoveredVault(
            vault=UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=(new_keyfile_path),
                password=password,
            ),
            entries=(),
            recovery_code=("UVR1-ROTATED-CODE"),
            replaced_existing_keys=(replace_existing_keys),
        )


class BlockingSecurityBackend:
    """Controllable asynchronous Security Center backend."""

    def __init__(
        self,
        *,
        block_snapshot: bool = False,
        block_add: bool = False,
        block_password: bool = False,
    ) -> None:
        self.block_snapshot = block_snapshot
        self.block_add = block_add
        self.block_password = block_password

        self.snapshot_started = threading.Event()
        self.snapshot_release = threading.Event()
        self.add_started = threading.Event()
        self.add_release = threading.Event()
        self.password_started = threading.Event()
        self.password_release = threading.Event()

    def snapshot(
        self,
        vault: UnlockedVault,
    ) -> SecuritySnapshot:
        vault.password_bytes()

        if self.block_snapshot:
            self.snapshot_started.set()
            _wait_for_release(self.snapshot_release)

        return SecuritySnapshot(
            keys=(
                UsbKeySummary(
                    key_id=KEY_ID,
                    is_current=True,
                ),
                UsbKeySummary(
                    key_id=BACKUP_KEY_ID,
                ),
            ),
            recovery_configured=True,
        )

    def add_key(
        self,
        vault: UnlockedVault,
        new_keyfile_path: Path,
    ) -> UsbKeySummary:
        del new_keyfile_path

        vault.password_bytes()

        if self.block_add:
            self.add_started.set()
            _wait_for_release(self.add_release)

        return UsbKeySummary(key_id=BACKUP_KEY_ID)

    def revoke_key(
        self,
        vault: UnlockedVault,
        key_id_hex: str,
    ) -> UsbKeySummary:
        del key_id_hex

        vault.password_bytes()

        return UsbKeySummary(key_id=BACKUP_KEY_ID)

    def change_password(
        self,
        vault: UnlockedVault,
        *,
        current_password: str,
        new_password: str,
        additional_keyfile_paths: tuple[
            Path,
            ...,
        ],
        recovery_code: str,
    ) -> PasswordUpdatedVault:
        del current_password
        del additional_keyfile_paths
        del recovery_code

        vault.password_bytes()

        if self.block_password:
            self.password_started.set()
            _wait_for_release(self.password_release)

        return PasswordUpdatedVault(
            vault=UnlockedVault.create(
                vault_path=vault.vault_path,
                keyfile_path=(vault.keyfile_path),
                password=new_password,
            ),
            entries=(),
            key_count=2,
            recovery_updated=True,
        )


def _session_guard() -> SessionGuard:
    return SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )


def _show_window(
    window: FullyAsyncSecurityMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _activate_vault(
    window: FullyAsyncSecurityMainWindow,
    tmp_path: Path,
) -> None:
    window._activate_vault(
        UnlockedVault.create(
            vault_path=(tmp_path / "Private.vault"),
            keyfile_path=(tmp_path / ".authkey"),
            password="old password",
        ),
        (),
    )
    QApplication.processEvents()


def _assert_gui_event_loop_runs(
    qtbot: QtBot,
) -> None:
    processed: list[bool] = []

    QTimer.singleShot(
        0,
        lambda: processed.append(True),
    )

    qtbot.waitUntil(
        lambda: bool(processed),
        timeout=1_000,
    )


def _wait_for_release(
    release: threading.Event,
) -> None:
    if not release.wait(timeout=3):
        raise RuntimeError("test release timed out")


def test_unlock_runs_in_background(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = BlockingUnlockBackend()
    window = FullyAsyncSecurityMainWindow(
        backend=backend,
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_unlock_requested(
        str(tmp_path / "Private.vault"),
        str(tmp_path / ".authkey"),
        "test password",
    )

    qtbot.waitUntil(
        backend.started.is_set,
        timeout=1_000,
    )

    try:
        assert window.is_busy
        assert not window._pages.isEnabled()
        assert not window.lock_action.isEnabled()
        _assert_gui_event_loop_runs(qtbot)
    finally:
        backend.release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.is_unlocked
    assert window.current_page_name == "vault"
    assert window.vault_page.table.rowCount() == 1


def test_setup_runs_in_background_and_presents_code(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = BlockingSetupBackend()
    presented_codes: list[str] = []

    window = FullyAsyncSecurityMainWindow(
        backend=ImmediateVaultBackend(),
        setup_backend=backend,
        recovery_presenter=(lambda parent, code: presented_codes.append(code)),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_setup_requested(
        str(tmp_path / "New.vault"),
        str(tmp_path / ".authkey"),
        "test password",
    )

    qtbot.waitUntil(
        backend.started.is_set,
        timeout=1_000,
    )

    try:
        assert window.is_busy
        _assert_gui_event_loop_runs(qtbot)
    finally:
        backend.release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.is_unlocked
    assert presented_codes == [
        "UVR1-NEW-SETUP-CODE",
    ]


def test_recovery_runs_in_background(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = BlockingRecoveryBackend()
    presented_codes: list[str] = []

    window = FullyAsyncSecurityMainWindow(
        backend=ImmediateVaultBackend(),
        recovery_backend=backend,
        recovery_presenter=(lambda parent, code: presented_codes.append(code)),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_recovery_requested(
        str(tmp_path / "Private.vault"),
        str(tmp_path / "replacement.authkey"),
        "test password",
        "UVR1-OLD-CODE",
        True,
    )

    qtbot.waitUntil(
        backend.started.is_set,
        timeout=1_000,
    )

    try:
        assert window.is_busy
        _assert_gui_event_loop_runs(qtbot)
    finally:
        backend.release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.is_unlocked
    assert presented_codes == [
        "UVR1-ROTATED-CODE",
    ]


def test_security_snapshot_runs_in_background(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = BlockingSecurityBackend(block_snapshot=True)
    window = FullyAsyncSecurityMainWindow(
        backend=ImmediateVaultBackend(),
        security_backend=backend,
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    window.show_security_page()

    qtbot.waitUntil(
        backend.snapshot_started.is_set,
        timeout=1_000,
    )

    try:
        assert window.is_busy
        assert window.current_page_name == "security"
        assert not window.lock_action.isEnabled()
        _assert_gui_event_loop_runs(qtbot)
    finally:
        backend.snapshot_release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.security_page.keys_table.rowCount() == 2


def test_backup_key_creation_runs_in_background(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = BlockingSecurityBackend(block_add=True)
    window = FullyAsyncSecurityMainWindow(
        backend=ImmediateVaultBackend(),
        security_backend=backend,
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    window._on_add_key_requested(str(tmp_path / "backup.authkey"))

    qtbot.waitUntil(
        backend.add_started.is_set,
        timeout=1_000,
    )

    try:
        assert window.is_busy
        assert not window.lock_action.isEnabled()
        _assert_gui_event_loop_runs(qtbot)
    finally:
        backend.add_release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.security_page.keys_table.rowCount() == 2


def test_password_change_runs_in_background(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = BlockingSecurityBackend(block_password=True)
    window = FullyAsyncSecurityMainWindow(
        backend=ImmediateVaultBackend(),
        security_backend=backend,
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    window._on_password_change_requested(
        "old password",
        "new password",
        (),
        "UVR1-CURRENT-CODE",
    )

    qtbot.waitUntil(
        backend.password_started.is_set,
        timeout=1_000,
    )

    try:
        assert window.is_busy
        assert not window.lock_action.isEnabled()
        _assert_gui_event_loop_runs(qtbot)
    finally:
        backend.password_release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.is_unlocked
    assert window._require_vault().password_bytes() == b"new password"
