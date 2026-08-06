"""Integration tests for automatic vault-library registration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import (
    QtBot,
)

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.usb_grace import (
    UsbGraceSessionGuard,
)
from usb_vault.ui.vault_library import (
    VaultLibraryStore,
)
from usb_vault.ui.vault_library_window import (
    VaultLibraryMainWindow,
)

KEY_ID = b"K" * 16
VAULT_ID = b"V" * 16
OPENED_AT = datetime(
    2026,
    8,
    6,
    21,
    0,
    tzinfo=UTC,
)


@dataclass
class FakeKeyfileProbe:
    """Keep the selected key available."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        del keyfile_path
        return KEY_ID


@dataclass
class FakeVaultIdentityReader:
    """Return one configured public vault identity."""

    vault_id: bytes = VAULT_ID

    def read_vault_id(
        self,
        vault_path: Path,
    ) -> bytes:
        del vault_path
        return self.vault_id


class FailingVaultIdentityReader:
    """Simulate a local registry update failure."""

    def read_vault_id(
        self,
        vault_path: Path,
    ) -> bytes:
        del vault_path
        raise OSError("simulated identity read failure")


class FakeVaultBackend:
    """Minimal successful inherited backend."""

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


def _clock() -> datetime:
    return OPENED_AT


def _session_guard() -> UsbGraceSessionGuard:
    return UsbGraceSessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=5_000,
    )


def _show_window(
    window: VaultLibraryMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def test_successful_unlock_registers_vault(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    keyfile_path = tmp_path / ".authkey"
    vault_path.write_bytes(b"placeholder")
    keyfile_path.write_bytes(b"placeholder")

    store = VaultLibraryStore(
        tmp_path / "vault-library.json",
        identity_reader=(FakeVaultIdentityReader()),
        clock=_clock,
    )

    window = VaultLibraryMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        vault_library=store,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_unlock_requested(
        str(vault_path),
        str(keyfile_path),
        "test password",
    )

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.is_unlocked
    assert window.last_library_error is None

    entries = store.list_entries()

    assert len(entries) == 1
    assert entries[0].vault_id == VAULT_ID
    assert entries[0].vault_path == vault_path
    assert entries[0].display_name == "Private"


def test_library_failure_does_not_cancel_unlock(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    keyfile_path = tmp_path / ".authkey"

    store = VaultLibraryStore(
        tmp_path / "vault-library.json",
        identity_reader=(FailingVaultIdentityReader()),
        clock=_clock,
    )

    window = VaultLibraryMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        vault_library=store,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_unlock_requested(
        str(vault_path),
        str(keyfile_path),
        "test password",
    )

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.is_unlocked
    assert window.last_library_error == ("simulated identity read failure")
