"""Integration tests for the card-based vault home screen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
from pathlib import Path

import pytest
from PySide6.QtCore import (
    Qt,
)
from PySide6.QtTest import (
    QTest,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
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
from usb_vault.ui.vault_cards_window import (
    VaultCardsMainWindow,
)
from usb_vault.ui.vault_library import (
    VaultLibraryStore,
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
    """Keep any selected test key available."""

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


class FakeVaultBackend:
    """Minimal successful desktop backend."""

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
    window: VaultCardsMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def test_window_starts_on_library_with_registered_card(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")
    store = _library_store(
        tmp_path=tmp_path,
        vault_path=vault_path,
    )

    window = VaultCardsMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        vault_library=store,
    )
    qtbot.addWidget(window)
    _show_window(window)

    assert window.current_page_name == "library"
    assert len(window.library_page.entries) == 1

    card = window.library_page.card_for_vault_id(VAULT_ID)
    assert card is not None
    assert card.entry.display_name == "Private Vault"


def test_clicking_card_opens_prefilled_unlock_form(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")
    store = _library_store(
        tmp_path=tmp_path,
        vault_path=vault_path,
    )

    window = VaultCardsMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        vault_library=store,
    )
    qtbot.addWidget(window)
    _show_window(window)

    card = window.library_page.card_for_vault_id(VAULT_ID)
    assert card is not None

    QTest.mouseClick(
        card.open_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert window.current_page_name == "unlock"
    assert window.unlock_page.vault_path_edit.text() == str(vault_path)
    assert window.unlock_page.keyfile_path_edit.text() == ""


def test_lock_returns_to_library(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    keyfile_path = tmp_path / ".authkey"
    vault_path.write_bytes(b"encrypted vault")
    keyfile_path.write_bytes(b"test key")

    store = _library_store(
        tmp_path=tmp_path,
        vault_path=vault_path,
    )

    window = VaultCardsMainWindow(
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
    assert window.current_page_name == "vault"

    window.lock_vault()
    QApplication.processEvents()

    assert not window.is_unlocked
    assert window.current_page_name == "library"
    assert len(window.library_page.entries) == 1


def test_add_existing_opens_selected_vault_for_unlock(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_vault = tmp_path / "Selected.vault"
    selected_vault.write_bytes(b"encrypted vault")

    store = VaultLibraryStore(
        tmp_path / "vault-library.json",
        identity_reader=(FakeVaultIdentityReader()),
        clock=_clock,
    )

    def select_vault(
        *args: object,
        **kwargs: object,
    ) -> tuple[str, str]:
        del args
        del kwargs

        return (
            str(selected_vault),
            ("USB Vault files (*.vault)"),
        )

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        select_vault,
    )

    window = VaultCardsMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        vault_library=store,
    )
    qtbot.addWidget(window)
    _show_window(window)

    QTest.mouseClick(
        window.library_page.add_existing_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert window.current_page_name == "unlock"
    assert window.unlock_page.vault_path_edit.text() == str(selected_vault)
    assert store.list_entries() == ()


def test_remove_card_does_not_delete_vault(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "Private.vault"
    original_bytes = b"encrypted vault bytes"
    vault_path.write_bytes(original_bytes)

    store = _library_store(
        tmp_path=tmp_path,
        vault_path=vault_path,
    )

    def confirm_removal(
        *args: object,
        **kwargs: object,
    ) -> QMessageBox.StandardButton:
        del args
        del kwargs

        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(
        QMessageBox,
        "question",
        confirm_removal,
    )

    window = VaultCardsMainWindow(
        backend=FakeVaultBackend(),
        session_guard=(_session_guard()),
        vault_library=store,
    )
    qtbot.addWidget(window)
    _show_window(window)

    window._on_library_remove_requested(VAULT_ID)
    QApplication.processEvents()

    assert store.list_entries() == ()
    assert vault_path.exists()
    assert vault_path.read_bytes() == original_bytes
    assert window.library_page.entries == ()
