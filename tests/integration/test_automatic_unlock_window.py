"""Integration tests for automatic USB-triggered unlocking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
from pathlib import Path

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtTest import (
    QTest,
)
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import (
    QtBot,
)

from usb_vault.core.errors import (
    UnlockError,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.automatic_unlock_window import (
    AutomaticUnlockMainWindow,
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

KEY_ID = b"K" * 16
VAULT_ID = b"V" * 16
PASSWORD = "test password"
OPENED_AT = datetime(
    2026,
    8,
    6,
    21,
    0,
    tzinfo=UTC,
)


@dataclass
class FakeKeyLocator:
    """Controllable mounted-key discovery."""

    result: Path | None = None
    calls: int = 0

    def find_matching_keyfile(
        self,
        vault_path: Path,
    ) -> Path | None:
        del vault_path

        self.calls += 1
        return self.result


@dataclass
class FakeKeyfileProbe:
    """Keep any detected test key available."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        del keyfile_path
        return KEY_ID


@dataclass
class FakeVaultIdentityReader:
    """Return one public vault identity."""

    def read_vault_id(
        self,
        vault_path: Path,
    ) -> bytes:
        del vault_path
        return VAULT_ID


class FakeVaultBackend:
    """Count unlock attempts and verify the supplied password."""

    def __init__(
        self,
        *,
        accepted_password: str = PASSWORD,
    ) -> None:
        self.accepted_password = accepted_password.encode("utf-8")
        self.unlock_calls = 0

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        self.unlock_calls += 1

        if vault.password_bytes() != self.accepted_password:
            raise UnlockError()

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


def _library_store(
    *,
    tmp_path: Path,
    vault_path: Path,
) -> VaultLibraryStore:
    store = VaultLibraryStore(
        tmp_path / "vault-library.json",
        identity_reader=(FakeVaultIdentityReader()),
        clock=_clock,
    )
    store.register_vault(
        vault_path,
        display_name="Private Vault",
    )

    return store


def _show_window(
    window: AutomaticUnlockMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _open_card_and_submit_password(
    window: AutomaticUnlockMainWindow,
    password: str,
) -> None:
    card = window.library_page.card_for_vault_id(VAULT_ID)
    assert card is not None

    QTest.mouseClick(
        card.open_button,
        Qt.MouseButton.LeftButton,
    )

    window.unlock_page.password_edit.setText(password)

    QTest.mouseClick(
        window.unlock_page.unlock_button,
        Qt.MouseButton.LeftButton,
    )


def test_waits_without_attempting_password_until_key_appears(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    keyfile_path = Path("/Volumes/USB/.authkey")
    locator = FakeKeyLocator()
    backend = FakeVaultBackend()

    window = AutomaticUnlockMainWindow(
        backend=backend,
        session_guard=_session_guard(),
        key_locator=locator,
        vault_library=_library_store(
            tmp_path=tmp_path,
            vault_path=vault_path,
        ),
        unlock_poll_interval_ms=20,
    )
    qtbot.addWidget(window)
    _show_window(window)

    _open_card_and_submit_password(
        window,
        PASSWORD,
    )

    qtbot.waitUntil(
        lambda: window.is_waiting_for_usb and locator.calls >= 2,
        timeout=2_000,
    )

    assert backend.unlock_calls == 0
    assert window.unlock_page.password_edit.text() == ""

    locator.result = keyfile_path

    qtbot.waitUntil(
        lambda: window.is_unlocked,
        timeout=3_000,
    )

    assert backend.unlock_calls == 1
    assert window._require_vault().keyfile_path == keyfile_path

    qtbot.wait(100)
    assert backend.unlock_calls == 1


def test_already_inserted_key_unlocks_automatically(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    locator = FakeKeyLocator(result=Path("/Volumes/USB/.authkey"))
    backend = FakeVaultBackend()

    window = AutomaticUnlockMainWindow(
        backend=backend,
        session_guard=_session_guard(),
        key_locator=locator,
        vault_library=_library_store(
            tmp_path=tmp_path,
            vault_path=vault_path,
        ),
        unlock_poll_interval_ms=20,
    )
    qtbot.addWidget(window)
    _show_window(window)

    _open_card_and_submit_password(
        window,
        PASSWORD,
    )

    qtbot.waitUntil(
        lambda: window.is_unlocked,
        timeout=3_000,
    )

    assert backend.unlock_calls == 1


def test_cancel_returns_to_library_without_unlock_attempt(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    locator = FakeKeyLocator()
    backend = FakeVaultBackend()

    window = AutomaticUnlockMainWindow(
        backend=backend,
        session_guard=_session_guard(),
        key_locator=locator,
        vault_library=_library_store(
            tmp_path=tmp_path,
            vault_path=vault_path,
        ),
        unlock_poll_interval_ms=20,
    )
    qtbot.addWidget(window)
    _show_window(window)

    _open_card_and_submit_password(
        window,
        PASSWORD,
    )

    qtbot.waitUntil(
        lambda: window.is_waiting_for_usb,
        timeout=1_000,
    )

    QTest.mouseClick(
        window.unlock_page.cancel_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert window.current_page_name == "library"
    assert not window.is_waiting_for_usb
    assert backend.unlock_calls == 0

    locator.result = Path("/Volumes/USB/.authkey")
    qtbot.wait(100)

    assert backend.unlock_calls == 0


def test_wrong_password_attempts_unlock_only_once(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    locator = FakeKeyLocator(result=Path("/Volumes/USB/.authkey"))
    backend = FakeVaultBackend()

    window = AutomaticUnlockMainWindow(
        backend=backend,
        session_guard=_session_guard(),
        key_locator=locator,
        vault_library=_library_store(
            tmp_path=tmp_path,
            vault_path=vault_path,
        ),
        unlock_poll_interval_ms=20,
    )
    qtbot.addWidget(window)
    _show_window(window)

    _open_card_and_submit_password(
        window,
        "wrong password",
    )

    qtbot.waitUntil(
        lambda: backend.unlock_calls == 1,
        timeout=2_000,
    )
    qtbot.waitUntil(
        lambda: not window.is_busy and window.unlock_page.error_label.isVisible(),
        timeout=2_000,
    )

    assert not window.is_unlocked
    assert not window.is_waiting_for_usb
    assert window.unlock_page.error_label.text() == "Unable to unlock vault."

    qtbot.wait(100)
    assert backend.unlock_calls == 1


def test_manual_keyfile_bypasses_waiter(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    keyfile_path = tmp_path / "manual.authkey"
    locator = FakeKeyLocator()
    backend = FakeVaultBackend()

    window = AutomaticUnlockMainWindow(
        backend=backend,
        session_guard=_session_guard(),
        key_locator=locator,
        vault_library=_library_store(
            tmp_path=tmp_path,
            vault_path=vault_path,
        ),
        unlock_poll_interval_ms=20,
    )
    qtbot.addWidget(window)
    _show_window(window)

    card = window.library_page.card_for_vault_id(VAULT_ID)
    assert card is not None

    QTest.mouseClick(
        card.open_button,
        Qt.MouseButton.LeftButton,
    )

    window.unlock_page.keyfile_path_edit.setText(str(keyfile_path))
    window.unlock_page.password_edit.setText(PASSWORD)

    QTest.mouseClick(
        window.unlock_page.unlock_button,
        Qt.MouseButton.LeftButton,
    )

    qtbot.waitUntil(
        lambda: window.is_unlocked,
        timeout=2_000,
    )

    assert locator.calls == 0
    assert backend.unlock_calls == 1
    assert window._require_vault().keyfile_path == keyfile_path
