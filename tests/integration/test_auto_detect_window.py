"""Integration tests for automatic mounted-USB selection."""

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
from usb_vault.ui.auto_detect_window import (
    AutoDetectUsbMainWindow,
    NO_MATCHING_USB_MESSAGE,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.usb_grace import (
    UsbGraceSessionGuard,
)

KEY_ID = b"K" * 16


@dataclass
class FakeKeyLocator:
    """Controllable mounted-key lookup."""

    result: Path | None
    calls: int = 0
    last_vault_path: Path | None = None

    def find_matching_keyfile(
        self,
        vault_path: Path,
    ) -> Path | None:
        self.calls += 1
        self.last_vault_path = vault_path
        return self.result


@dataclass
class FakeKeyfileProbe:
    """Keep the selected test key available."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        del keyfile_path
        return KEY_ID


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


def _session_guard() -> UsbGraceSessionGuard:
    return UsbGraceSessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=5_000,
    )


def _show_window(
    window: AutoDetectUsbMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def test_blank_keyfile_uses_detected_usb(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    detected_keyfile = tmp_path / ".authkey"
    locator = FakeKeyLocator(result=detected_keyfile)

    window = AutoDetectUsbMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        key_locator=locator,
    )
    qtbot.addWidget(window)
    _show_window(window)

    vault_path = tmp_path / "Private.vault"

    window._on_unlock_requested(
        str(vault_path),
        "",
        "test password",
    )

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert locator.calls == 1
    assert locator.last_vault_path == vault_path
    assert window.is_unlocked
    assert window._require_vault().keyfile_path == detected_keyfile
    assert window.statusBar().currentMessage() == ("Vault unlocked using the detected USB key.")


def test_explicit_keyfile_bypasses_detection(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    locator = FakeKeyLocator(result=None)
    explicit_keyfile = tmp_path / "manual.authkey"

    window = AutoDetectUsbMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        key_locator=locator,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_unlock_requested(
        str(tmp_path / "Private.vault"),
        str(explicit_keyfile),
        "test password",
    )

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert locator.calls == 0
    assert window.is_unlocked
    assert window._require_vault().keyfile_path == explicit_keyfile


def test_missing_matching_usb_shows_error(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    locator = FakeKeyLocator(result=None)

    window = AutoDetectUsbMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        key_locator=locator,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_unlock_requested(
        str(tmp_path / "Private.vault"),
        "",
        "test password",
    )

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert not window.is_unlocked
    assert window.unlock_page.error_label.text() == NO_MATCHING_USB_MESSAGE
