"""Integration tests for desktop window navigation and actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.errors import (
    UnlockError,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.main_window import (
    MainWindow,
)


@dataclass
class FakeBackend:
    """In-memory backend used to test desktop coordination."""

    entries: tuple[
        VaultEntrySummary,
        ...,
    ] = (
        VaultEntrySummary(
            name="notes.txt",
            size=12,
        ),
    )
    unlock_error: Exception | None = None
    added_paths: list[Path] = field(default_factory=list)
    extracted: list[
        tuple[
            str,
            Path,
            bool,
        ]
    ] = field(default_factory=list)
    deleted_names: list[str] = field(default_factory=list)

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        vault.password_bytes()

        if self.unlock_error is not None:
            raise self.unlock_error

        return self.entries

    def list_entries(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        vault.password_bytes()
        return self.entries

    def add_file(
        self,
        vault: UnlockedVault,
        source_path: Path,
        stored_name: str | None = None,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        self.added_paths.append(source_path)

        result = VaultEntrySummary(
            name=(stored_name or source_path.name),
            size=20,
        )
        self.entries = (
            *self.entries,
            result,
        )

        return result

    def extract_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        self.extracted.append(
            (
                stored_name,
                destination_path,
                overwrite,
            )
        )

        return next(entry for entry in self.entries if entry.name == stored_name)

    def delete_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
    ) -> VaultEntrySummary:
        vault.password_bytes()

        removed = next(entry for entry in self.entries if entry.name == stored_name)

        self.deleted_names.append(stored_name)
        self.entries = tuple(entry for entry in self.entries if entry.name != stored_name)

        return removed


def _show_window(
    window: MainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _fill_unlock_page(
    window: MainWindow,
) -> None:
    window.unlock_page.vault_path_edit.setText("/tmp/Private.vault")
    window.unlock_page.keyfile_path_edit.setText("/Volumes/USB/.authkey")
    window.unlock_page.password_edit.setText("test password")


def _click_unlock(
    window: MainWindow,
) -> None:
    QTest.mouseClick(
        window.unlock_page.unlock_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()


def test_successful_unlock_opens_vault_browser(
    qtbot: QtBot,
) -> None:
    backend = FakeBackend()
    window = MainWindow(backend=backend)
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    assert window.is_unlocked
    assert window.current_page_name == "vault"
    assert window.vault_page.table.rowCount() == 1
    assert window.unlock_page.password_edit.text() == ""


def test_failed_unlock_remains_locked(
    qtbot: QtBot,
) -> None:
    backend = FakeBackend(unlock_error=UnlockError())
    window = MainWindow(backend=backend)
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    assert not window.is_unlocked
    assert window.current_page_name == "unlock"
    assert window.unlock_page.error_label.text() == "Unable to unlock vault."


def test_manual_lock_returns_to_unlock_page(
    qtbot: QtBot,
) -> None:
    window = MainWindow(backend=FakeBackend())
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    QTest.mouseClick(
        window.vault_page.lock_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert not window.is_unlocked
    assert window.current_page_name == "unlock"
    assert window.vault_page.table.rowCount() == 0


def test_file_actions_refresh_browser(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = FakeBackend()
    window = MainWindow(backend=backend)
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    source = tmp_path / "new.txt"

    assert window.add_file_from_path(source)
    assert backend.added_paths == [
        source,
    ]
    assert window.vault_page.table.rowCount() == 2

    destination = tmp_path / "notes.txt"

    assert window.extract_entry_to(
        "notes.txt",
        destination,
        overwrite=True,
    )
    assert backend.extracted == [
        (
            "notes.txt",
            destination,
            True,
        ),
    ]

    assert window.delete_entry("notes.txt")
    assert backend.deleted_names == [
        "notes.txt",
    ]
    assert window.vault_page.table.rowCount() == 1
