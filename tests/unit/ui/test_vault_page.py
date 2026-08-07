"""Tests for the unlocked vault browser page."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
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


def _row_kind(page: VaultPage, row: int) -> tuple[str, str]:
    item = page.table.item(row, 0)
    assert item is not None
    kind, value = item.data(Qt.ItemDataRole.UserRole)
    return kind, value


def test_nested_entries_show_as_a_folder_at_root(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/Taxes/2024.pdf", size=100),
            VaultEntrySummary(name="Keep.txt", size=10),
        )
    )

    assert page.table.rowCount() == 2
    assert _table_text(page, 0, 0) == "Documents"
    assert _row_kind(page, 0) == ("folder", "Documents")
    assert _table_text(page, 1, 0) == "Keep.txt"
    assert _row_kind(page, 1) == ("file", "Keep.txt")


def test_empty_folder_marker_shows_folder_without_a_visible_file(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/.vaultkeep", size=0),))

    assert page.table.rowCount() == 1
    assert _row_kind(page, 0) == ("folder", "Documents")


def test_double_click_folder_navigates_in_and_breadcrumb_updates(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/Taxes/2024.pdf", size=100),
        )
    )

    page.table.selectRow(0)
    item = page.table.item(0, 0)
    assert item is not None
    page._on_row_activated(item)

    assert page.current_folder == "Documents"
    assert page.table.rowCount() == 1
    assert _table_text(page, 0, 0) == "Taxes"

    # Root breadcrumb link navigates back out.
    root_button = page._breadcrumb_layout.itemAt(0).widget()
    assert isinstance(root_button, QPushButton)
    QTest.mouseClick(root_button, Qt.MouseButton.LeftButton)

    assert page.current_folder == ""
    assert _table_text(page, 0, 0) == "Documents"


def test_new_folder_button_emits_signal(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    with qtbot.waitSignal(
        page.create_folder_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.new_folder_button,
            Qt.MouseButton.LeftButton,
        )


def test_selecting_a_folder_enables_delete_and_disables_export(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/.vaultkeep", size=0),))
    page.table.selectRow(0)

    assert not page.extract_button.isEnabled()
    assert page.delete_button.isEnabled()
    assert page.delete_button.text() == "Delete folder"
    assert page.selected_name() is None
    assert page.selected_folder_path() == "Documents"


def test_delete_folder_button_emits_full_path(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/Taxes/.vaultkeep", size=0),
        )
    )
    page.table.selectRow(0)
    page._on_row_activated(page.table.item(0, 0))
    page.table.selectRow(0)

    with qtbot.waitSignal(
        page.delete_folder_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.delete_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == ["Documents/Taxes"]


def test_adding_files_targets_the_open_folder(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/.vaultkeep", size=0),))
    page.table.selectRow(0)
    page._on_row_activated(page.table.item(0, 0))

    assert page.current_folder == "Documents"


def test_deleting_the_open_folder_falls_back_to_root(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/.vaultkeep", size=0),))
    page.table.selectRow(0)
    page._on_row_activated(page.table.item(0, 0))
    assert page.current_folder == "Documents"

    # The folder was removed server-side; the next refresh must not leave the
    # page pointed at a path that no longer exists.
    page.set_entries(())

    assert page.current_folder == ""


def test_empty_state_wording_is_contextual(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(())
    assert page.empty_title.text() == "This vault is empty"

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/.vaultkeep", size=0),
            VaultEntrySummary(name="Documents/Taxes/.vaultkeep", size=0),
        )
    )
    page.table.selectRow(0)
    page._on_row_activated(page.table.item(0, 0))
    page.set_entries(
        (
            VaultEntrySummary(name="Documents/.vaultkeep", size=0),
        )
    )

    assert page.current_folder == "Documents"
    assert page.empty_title.text() == "This folder is empty"


def test_dropping_a_file_onto_a_folder_emits_move_requested(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/.vaultkeep", size=0),
            VaultEntrySummary(name="notes.txt", size=10),
        )
    )

    with qtbot.waitSignal(
        page.move_requested,
        timeout=1_000,
    ) as signal:
        page._handle_drop("file", "notes.txt", "Documents")

    assert signal.args == ["notes.txt", "Documents/notes.txt"]


def test_dropping_a_file_onto_root_moves_it_out_of_a_folder(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/notes.txt", size=10),))

    with qtbot.waitSignal(
        page.move_requested,
        timeout=1_000,
    ) as signal:
        page._handle_drop("file", "Documents/notes.txt", "")

    assert signal.args == ["Documents/notes.txt", "notes.txt"]


def test_dropping_a_file_onto_its_current_folder_is_a_no_op(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/notes.txt", size=10),))

    received = []
    page.move_requested.connect(lambda *args: received.append(args))
    page._handle_drop("file", "Documents/notes.txt", "Documents")
    QApplication.processEvents()

    assert received == []


def test_dropping_a_folder_onto_another_folder_emits_move_folder_requested(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/.vaultkeep", size=0),
            VaultEntrySummary(name="Archive/.vaultkeep", size=0),
        )
    )

    with qtbot.waitSignal(
        page.move_folder_requested,
        timeout=1_000,
    ) as signal:
        page._handle_drop("folder", "Documents", "Archive")

    assert signal.args == ["Documents", "Archive"]


def test_dropping_a_folder_into_itself_or_its_own_descendant_is_rejected(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries((VaultEntrySummary(name="Documents/Taxes/.vaultkeep", size=0),))

    received = []
    page.move_folder_requested.connect(lambda *args: received.append(args))
    page._handle_drop("folder", "Documents", "Documents")
    page._handle_drop("folder", "Documents", "Documents/Taxes")
    QApplication.processEvents()

    assert received == []


def test_table_drop_indicator_only_targets_folder_rows(
    qtbot: QtBot,
) -> None:
    page = VaultPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_entries(
        (
            VaultEntrySummary(name="Documents/.vaultkeep", size=0),
            VaultEntrySummary(name="notes.txt", size=10),
        )
    )

    folder_row_rect = page.table.visualItemRect(page.table.item(0, 0))
    file_row_rect = page.table.visualItemRect(page.table.item(1, 0))

    assert page.table._folder_target_at(folder_row_rect.center()) == "Documents"
    assert page.table._folder_target_at(file_row_rect.center()) is None
