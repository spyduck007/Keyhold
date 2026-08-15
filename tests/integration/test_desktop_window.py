"""Integration tests for desktop window navigation and actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.errors import (
    UnlockError,
    VaultOperationError,
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
from usb_vault.ui.setup_backend import (
    CreatedVault,
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
    added_stored_names: list[str | None] = field(default_factory=list)
    extracted: list[
        tuple[
            str,
            Path,
            bool,
        ]
    ] = field(default_factory=list)
    deleted_names: list[str] = field(default_factory=list)
    created_folders: list[str] = field(default_factory=list)
    deleted_folders: list[str] = field(default_factory=list)

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
        self.added_stored_names.append(stored_name)

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

    def create_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> VaultEntrySummary:
        vault.password_bytes()
        self.created_folders.append(folder_path)

        result = VaultEntrySummary(
            name=f"{folder_path}/.vaultkeep",
            size=0,
        )
        self.entries = (
            *self.entries,
            result,
        )

        return result

    def delete_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> tuple[VaultEntrySummary, ...]:
        vault.password_bytes()
        self.deleted_folders.append(folder_path)

        prefix = f"{folder_path}/"
        removed = tuple(entry for entry in self.entries if entry.name.startswith(prefix))
        self.entries = tuple(entry for entry in self.entries if not entry.name.startswith(prefix))

        return removed


@dataclass
class FakeSetupBackend:
    """In-memory setup backend."""

    created_requests: list[
        tuple[
            Path,
            Path,
            str,
        ]
    ] = field(default_factory=list)

    def create_vault(
        self,
        *,
        vault_path: Path,
        keyfile_path: Path,
        password: str,
    ) -> CreatedVault:
        self.created_requests.append(
            (
                vault_path,
                keyfile_path,
                password,
            )
        )

        return CreatedVault(
            vault=UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                password=password,
            ),
            entries=(),
            recovery_code=("UVR1-TEST-RECOVERY-CODE"),
        )


class FailingAddBackend(FakeBackend):
    """Backend that exposes an add-file error."""

    def add_file(
        self,
        vault: UnlockedVault,
        source_path: Path,
        stored_name: str | None = None,
    ) -> VaultEntrySummary:
        del source_path
        del stored_name

        vault.password_bytes()
        raise VaultOperationError("Large-file test failure.")


def test_single_add_failure_preserves_detailed_error(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = MainWindow(backend=FailingAddBackend())
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    result = window.add_files_from_paths((tmp_path / "large.bin",))

    assert result == (
        0,
        1,
    )
    assert window.statusBar().currentMessage() == "Large-file test failure."


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


def test_sidebar_exposes_primary_navigation(
    qtbot: QtBot,
) -> None:
    window = MainWindow(backend=FakeBackend())
    qtbot.addWidget(window)
    _show_window(window)

    new_vault_button = window.sidebar.item_button("new")
    vaults_button = window.sidebar.item_button("vaults")
    lock_button = window.sidebar.item_button("lock")

    assert new_vault_button is not None
    assert vaults_button is not None
    assert lock_button is not None
    assert not lock_button.isEnabled()

    QTest.mouseClick(new_vault_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert window.current_page_name == "setup"

    QTest.mouseClick(vaults_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert window.current_page_name == "unlock"

    _fill_unlock_page(window)
    _click_unlock(window)
    assert lock_button.isEnabled()

    QTest.mouseClick(lock_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert window.current_page_name == "unlock"
    assert not window.is_unlocked


def test_window_uses_keyhold_product_name(
    qtbot: QtBot,
) -> None:
    window = MainWindow(backend=FakeBackend())
    qtbot.addWidget(window)

    assert window.windowTitle() == "Keyhold"
    brand_label = window.sidebar.findChild(QLabel, "sidebarBrandName")
    assert brand_label is not None
    assert brand_label.text() == "Keyhold"


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


def test_folder_actions_refresh_browser(
    qtbot: QtBot,
) -> None:
    backend = FakeBackend()
    window = MainWindow(backend=backend)
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    assert window.create_folder("Documents")
    assert backend.created_folders == ["Documents"]
    assert window.vault_page.table.rowCount() == 2

    row_kinds = {
        window.vault_page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        for row in range(window.vault_page.table.rowCount())
    }
    assert ("folder", "Documents") in row_kinds

    assert window.delete_folder("Documents")
    assert backend.deleted_folders == ["Documents"]
    assert window.vault_page.table.rowCount() == 1


def test_adding_a_file_inside_an_open_folder_uses_a_prefixed_name(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = FakeBackend(entries=(VaultEntrySummary(name="Documents/.vaultkeep", size=0),))
    window = MainWindow(backend=backend)
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    folder_item = window.vault_page.table.item(0, 0)
    window.vault_page.table.selectRow(0)
    window.vault_page._on_row_activated(folder_item)
    assert window.vault_page.current_folder == "Documents"

    source = tmp_path / "2024.pdf"
    assert window.add_file_from_path(source)
    assert backend.added_stored_names == ["Documents/2024.pdf"]


def test_new_vault_setup_opens_created_vault(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    setup_backend = FakeSetupBackend()
    presented_codes: list[str] = []

    def present_recovery_code(
        parent: QWidget,
        recovery_code: str,
    ) -> None:
        assert parent.objectName() == ("mainWindow")
        presented_codes.append(recovery_code)

    window = MainWindow(
        backend=FakeBackend(entries=()),
        setup_backend=setup_backend,
        recovery_presenter=(present_recovery_code),
    )
    qtbot.addWidget(window)
    _show_window(window)

    vault_path = tmp_path / "New.vault"
    keyfile_path = tmp_path / ".authkey"

    window.show_setup_page()

    window.setup_page.vault_path_edit.setText(str(vault_path))
    window.setup_page.keyfile_path_edit.setText(str(keyfile_path))
    window.setup_page.password_edit.setText("new password")
    window.setup_page.confirmation_edit.setText("new password")

    QTest.mouseClick(
        window.setup_page.create_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert setup_backend.created_requests == [
        (
            vault_path,
            keyfile_path,
            "new password",
        ),
    ]
    assert presented_codes == [
        "UVR1-TEST-RECOVERY-CODE",
    ]
    assert window.is_unlocked
    assert window.current_page_name == "vault"
    assert window.setup_page.password_edit.text() == ""
    assert window.unlock_page.vault_path_edit.text() == str(vault_path)


def test_multiple_file_imports_are_processed(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    backend = FakeBackend(entries=())
    window = MainWindow(backend=backend)
    qtbot.addWidget(window)
    _show_window(window)

    _fill_unlock_page(window)
    _click_unlock(window)

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"

    result = window.add_files_from_paths(
        (
            first,
            second,
        )
    )

    assert result == (
        2,
        0,
    )
    assert backend.added_paths == [
        first,
        second,
    ]
    assert window.vault_page.table.rowCount() == 2
