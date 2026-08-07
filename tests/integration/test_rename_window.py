"""Integration tests for asynchronous desktop file renaming."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
from usb_vault.ui.background_backend import (
    BackgroundVaultCredentials,
)
from usb_vault.ui.rename_backend import (
    MoveFolderResult,
    RenameFileResult,
)
from usb_vault.ui.rename_window import (
    RenameMainWindow,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)

KEY_ID = b"K" * 16


@dataclass
class FakeKeyfileProbe:
    """Keep the test USB identity available."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        del keyfile_path
        return KEY_ID


class FakeVaultBackend:
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


class FakeRenameBackend:
    """Immediate successful rename backend."""

    def rename_file(
        self,
        credentials: (BackgroundVaultCredentials),
        stored_name: str,
        new_name: str,
    ) -> RenameFileResult:
        credentials.password_bytes()
        del stored_name

        renamed = VaultEntrySummary(
            name=new_name,
            size=12,
        )

        return RenameFileResult(
            renamed=renamed,
            entries=(renamed,),
        )

    def move_folder(
        self,
        credentials: (BackgroundVaultCredentials),
        folder_path: str,
        destination_folder_path: str,
    ) -> MoveFolderResult:
        credentials.password_bytes()

        moved = VaultEntrySummary(
            name=(
                f"{destination_folder_path}/{folder_path}/file.bin"
                if destination_folder_path
                else f"{folder_path}/file.bin"
            ),
            size=12,
        )

        return MoveFolderResult(
            moved=(moved,),
            entries=(moved,),
        )


def _session_guard() -> SessionGuard:
    return SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )


def _show_window(
    window: RenameMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _activate_vault(
    window: RenameMainWindow,
    tmp_path: Path,
) -> None:
    window._activate_vault(
        UnlockedVault.create(
            vault_path=(tmp_path / "Private.vault"),
            keyfile_path=(tmp_path / ".authkey"),
            password="test password",
        ),
        (
            VaultEntrySummary(
                name="old.txt",
                size=12,
            ),
        ),
    )
    QApplication.processEvents()


def test_background_rename_updates_browser(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = RenameMainWindow(
        backend=FakeVaultBackend(),
        rename_backend=(FakeRenameBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    started = window.start_rename_entry(
        "old.txt",
        "new.txt",
    )

    assert started

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.vault_page.table.rowCount() == 1

    item = window.vault_page.table.item(0, 0)
    assert item is not None
    assert item.text() == "new.txt"

    assert window.statusBar().currentMessage() == ("Renamed old.txt to new.txt.")


def test_rename_action_tracks_selection(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = RenameMainWindow(
        backend=FakeVaultBackend(),
        rename_backend=(FakeRenameBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    assert not (window.rename_action.isEnabled())

    window.vault_page.table.selectRow(0)
    QApplication.processEvents()

    assert window.rename_action.isEnabled()

    window.lock_vault()

    assert not (window.rename_action.isEnabled())


def test_background_move_folder_updates_browser(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = RenameMainWindow(
        backend=FakeVaultBackend(),
        rename_backend=(FakeRenameBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    started = window.start_move_folder(
        "Documents",
        "Archive",
    )

    assert started

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.statusBar().currentMessage() == ("Moved Documents to Archive.")


def test_dragging_a_file_onto_a_folder_triggers_a_background_move(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = RenameMainWindow(
        backend=FakeVaultBackend(),
        rename_backend=(FakeRenameBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    window.vault_page.move_requested.emit("old.txt", "Documents/old.txt")

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.statusBar().currentMessage() == ("Renamed old.txt to Documents/old.txt.")


def test_dragging_a_folder_onto_another_folder_triggers_a_background_move(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = RenameMainWindow(
        backend=FakeVaultBackend(),
        rename_backend=(FakeRenameBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_vault(
        window,
        tmp_path,
    )

    window.vault_page.move_folder_requested.emit("Documents", "Archive")

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.statusBar().currentMessage() == ("Moved Documents to Archive.")
