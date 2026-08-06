"""Tests for the card-based vault-library page."""

from __future__ import annotations

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

from usb_vault.ui.pages.vault_library_page import (
    VaultLibraryPage,
)
from usb_vault.ui.vault_library import (
    VaultLibraryEntry,
)

VAULT_ID_A = b"A" * 16
VAULT_ID_B = b"B" * 16
OPENED_AT = datetime(
    2026,
    8,
    6,
    21,
    0,
    tzinfo=UTC,
)


def _entry(
    *,
    vault_id: bytes,
    display_name: str,
    vault_path: Path,
) -> VaultLibraryEntry:
    return VaultLibraryEntry(
        vault_id=vault_id,
        display_name=display_name,
        vault_path=vault_path,
        last_opened_at=OPENED_AT,
    )


def _show_page(
    page: VaultLibraryPage,
) -> None:
    page.show()
    QApplication.processEvents()


def test_page_shows_empty_state(
    qtbot: QtBot,
) -> None:
    page = VaultLibraryPage()
    qtbot.addWidget(page)
    _show_page(page)

    assert page.entries == ()

    empty_label = page.findChild(
        object,
        "emptyVaultLibraryLabel",
    )
    assert empty_label is not None


def test_available_card_emits_open_request(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    page = VaultLibraryPage()
    qtbot.addWidget(page)
    page.set_entries(
        (
            _entry(
                vault_id=VAULT_ID_A,
                display_name="Private",
                vault_path=vault_path,
            ),
        )
    )
    _show_page(page)

    card = page.card_for_vault_id(VAULT_ID_A)
    assert card is not None
    assert card.open_button.isEnabled()

    with qtbot.waitSignal(
        page.open_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            card.open_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        VAULT_ID_A,
    ]


def test_missing_vault_card_is_unavailable(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    page = VaultLibraryPage()
    qtbot.addWidget(page)
    page.set_entries(
        (
            _entry(
                vault_id=VAULT_ID_A,
                display_name="Missing",
                vault_path=(tmp_path / "Missing.vault"),
            ),
        )
    )
    _show_page(page)

    card = page.card_for_vault_id(VAULT_ID_A)
    assert card is not None
    assert not card.open_button.isEnabled()
    assert card.rename_button.isEnabled()
    assert card.remove_button.isEnabled()


def test_card_emits_rename_and_remove_requests(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault")

    page = VaultLibraryPage()
    qtbot.addWidget(page)
    page.set_entries(
        (
            _entry(
                vault_id=VAULT_ID_B,
                display_name="Private",
                vault_path=vault_path,
            ),
        )
    )
    _show_page(page)

    card = page.card_for_vault_id(VAULT_ID_B)
    assert card is not None

    with qtbot.waitSignal(
        page.rename_requested,
        timeout=1_000,
    ) as rename_signal:
        QTest.mouseClick(
            card.rename_button,
            Qt.MouseButton.LeftButton,
        )

    assert rename_signal.args == [
        VAULT_ID_B,
    ]

    with qtbot.waitSignal(
        page.remove_requested,
        timeout=1_000,
    ) as remove_signal:
        QTest.mouseClick(
            card.remove_button,
            Qt.MouseButton.LeftButton,
        )

    assert remove_signal.args == [
        VAULT_ID_B,
    ]


def test_action_buttons_emit_requests(
    qtbot: QtBot,
) -> None:
    page = VaultLibraryPage()
    qtbot.addWidget(page)
    _show_page(page)

    with qtbot.waitSignal(
        page.create_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.create_button,
            Qt.MouseButton.LeftButton,
        )

    with qtbot.waitSignal(
        page.add_existing_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.add_existing_button,
            Qt.MouseButton.LeftButton,
        )

    with qtbot.waitSignal(
        page.refresh_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.refresh_button,
            Qt.MouseButton.LeftButton,
        )
