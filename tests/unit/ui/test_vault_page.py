"""Tests for the unlocked vault browser page."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.pages.vault_page import (
    VaultPage,
)


def _show_page(
    page: VaultPage,
) -> None:
    page.show()
    QApplication.processEvents()


def _table_text(
    page: VaultPage,
    row: int,
    column: int,
) -> str:
    item = page.table.item(
        row,
        column,
    )

    assert item is not None

    return item.text()


def test_vault_page_displays_entries(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(
                name="notes.txt",
                size=1_024,
            ),
            VaultEntrySummary(
                name="photo.jpg",
                size=2_048,
            ),
        )
    )

    assert page.table.rowCount() == 2
    assert (
        _table_text(
            page,
            0,
            0,
        )
        == "notes.txt"
    )
    assert (
        _table_text(
            page,
            0,
            1,
        )
        == "1.0 KiB"
    )


def test_selection_enables_entry_actions(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(
                name="notes.txt",
                size=10,
            ),
        )
    )

    assert not page.extract_button.isEnabled()
    assert not page.delete_button.isEnabled()

    page.table.selectRow(0)

    assert page.extract_button.isEnabled()
    assert page.delete_button.isEnabled()
    assert page.selected_name() == "notes.txt"


def test_export_button_emits_selected_name(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(
                name="notes.txt",
                size=10,
            ),
        )
    )
    page.table.selectRow(0)

    with qtbot.waitSignal(
        page.extract_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.extract_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        "notes.txt",
    ]


def test_lock_button_emits_signal(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    with qtbot.waitSignal(
        page.lock_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.lock_button,
            Qt.MouseButton.LeftButton,
        )
