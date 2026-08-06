"""Integration tests for monitored desktop auto-locking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.monitored_window import (
    MonitoredMainWindow,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)

KEY_ID = b"K" * 16
KEYFILE_PATH = Path("/Volumes/TestUSB/.authkey")


@dataclass
class FakeKeyfileProbe:
    """Controllable USB key identity."""

    key_id: bytes | None = KEY_ID

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        assert keyfile_path == KEYFILE_PATH
        return self.key_id


class FakeBackend:
    """Minimal backend for monitored-window tests."""

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
        return (
            VaultEntrySummary(
                name="notes.txt",
                size=12,
            ),
        )

    def add_file(
        self,
        vault: UnlockedVault,
        source_path: Path,
        stored_name: str | None = None,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        return VaultEntrySummary(
            name=(stored_name or source_path.name),
            size=12,
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
            size=12,
        )

    def delete_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        return VaultEntrySummary(
            name=stored_name,
            size=12,
        )


def _show_window(
    window: MonitoredMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _unlock_window(
    window: MonitoredMainWindow,
) -> None:
    window.unlock_page.vault_path_edit.setText("/tmp/Private.vault")
    window.unlock_page.keyfile_path_edit.setText(str(KEYFILE_PATH))
    window.unlock_page.password_edit.setText("test password")

    QTest.mouseClick(
        window.unlock_page.unlock_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert window.is_unlocked


def test_usb_removal_locks_open_window(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe()
    guard = SessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    window = MonitoredMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _unlock_window(window)

    probe.key_id = None
    guard.check_keyfile_now()
    QApplication.processEvents()

    assert not window.is_unlocked
    assert window.current_page_name == "unlock"
    assert window.statusBar().currentMessage() == (
        "USB keyfile removed, changed, or unavailable. Vault locked."
    )


def test_keyfile_replacement_locks_open_window(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe()
    guard = SessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    window = MonitoredMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _unlock_window(window)

    probe.key_id = b"X" * 16
    guard.check_keyfile_now()
    QApplication.processEvents()

    assert not window.is_unlocked


def test_idle_timeout_locks_open_window(
    qtbot: QtBot,
) -> None:
    guard = SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=30,
    )
    window = MonitoredMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _unlock_window(window)

    qtbot.waitUntil(
        lambda: not window.is_unlocked,
        timeout=1_000,
    )

    assert window.current_page_name == "unlock"
    assert window.statusBar().currentMessage() == ("Vault locked after the inactivity timeout.")


def test_manual_lock_stops_monitoring(
    qtbot: QtBot,
) -> None:
    guard = SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    window = MonitoredMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _unlock_window(window)

    window.lock_vault()

    assert not guard.is_active
    assert not window.is_unlocked
