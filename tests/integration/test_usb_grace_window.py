"""Integration tests for desktop USB reconnection grace handling."""

from __future__ import annotations

from dataclasses import dataclass
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
from usb_vault.ui.usb_grace_window import (
    UsbGraceMainWindow,
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
    """Minimal inherited desktop backend."""

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


def _show_window(
    window: UsbGraceMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _activate_vault(
    window: UsbGraceMainWindow,
    tmp_path: Path,
) -> None:
    window._activate_vault(
        UnlockedVault.create(
            vault_path=(tmp_path / "Private.vault"),
            keyfile_path=(KEYFILE_PATH),
            password=("test password"),
        ),
        (),
    )
    QApplication.processEvents()


def test_missing_key_shows_warning_without_immediate_lock(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    probe = FakeKeyfileProbe()
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=5_000,
    )
    window = UsbGraceMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_grace_started,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    QApplication.processEvents()

    assert window.is_unlocked
    assert window.statusBar().currentMessage() == (
        "USB key unavailable. Reinsert the same key within 5 second(s) to keep the vault unlocked."
    )


def test_restored_key_keeps_vault_unlocked(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    probe = FakeKeyfileProbe()
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=5_000,
    )
    window = UsbGraceMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_grace_started,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    probe.key_id = KEY_ID

    with qtbot.waitSignal(
        guard.usb_key_restored,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    QApplication.processEvents()

    assert window.is_unlocked
    assert window.current_page_name == "vault"
    assert window.statusBar().currentMessage() == ("USB key restored. Vault remains unlocked.")


def test_expired_grace_locks_vault(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    probe = FakeKeyfileProbe()
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=50,
    )
    window = UsbGraceMainWindow(
        backend=FakeBackend(),
        session_guard=guard,
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    probe.key_id = None
    guard.check_keyfile_now()

    qtbot.waitUntil(
        lambda: not window.is_unlocked,
        timeout=1_000,
    )

    assert window.current_page_name == "unlock"
    assert window.statusBar().currentMessage() == (
        "USB key remained unavailable after the reconnection period. Vault locked."
    )
