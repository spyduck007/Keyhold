"""Integration tests for responsive desktop file operations."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.async_window import (
    AsyncSecurityMainWindow,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.background_backend import (
    AddFilesResult,
    BackgroundVaultCredentials,
    CreateFolderResult,
    DeleteFileResult,
    DeleteFolderResult,
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
    """Normal backend used only by inherited window behavior."""

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
        del source_path
        vault.password_bytes()

        return VaultEntrySummary(
            name=stored_name or "file.bin",
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

    def create_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> VaultEntrySummary:
        vault.password_bytes()

        return VaultEntrySummary(
            name=f"{folder_path}/.vaultkeep",
            size=0,
        )

    def delete_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> tuple[VaultEntrySummary, ...]:
        vault.password_bytes()

        return (
            VaultEntrySummary(
                name=f"{folder_path}/file.bin",
                size=1,
            ),
        )


class FakeBackgroundBackend:
    """Immediate successful background operations."""

    def add_files(
        self,
        credentials: BackgroundVaultCredentials,
        source_paths: tuple[Path, ...],
        *,
        folder_path: str = "",
    ) -> AddFilesResult:
        credentials.password_bytes()

        added = tuple(
            VaultEntrySummary(
                name=(f"{folder_path}/{path.name}" if folder_path else path.name),
                size=12,
            )
            for path in source_paths
        )

        return AddFilesResult(
            added=added,
            failures=(),
            entries=added,
        )

    def extract_file(
        self,
        credentials: BackgroundVaultCredentials,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        del destination_path
        del overwrite
        credentials.password_bytes()

        return VaultEntrySummary(
            name=stored_name,
            size=12,
        )

    def delete_file(
        self,
        credentials: BackgroundVaultCredentials,
        stored_name: str,
    ) -> DeleteFileResult:
        credentials.password_bytes()

        return DeleteFileResult(
            deleted=VaultEntrySummary(
                name=stored_name,
                size=12,
            ),
            entries=(),
        )

    def create_folder(
        self,
        credentials: BackgroundVaultCredentials,
        folder_path: str,
    ) -> CreateFolderResult:
        credentials.password_bytes()
        created = VaultEntrySummary(
            name=f"{folder_path}/.vaultkeep",
            size=0,
        )

        return CreateFolderResult(
            created=created,
            entries=(created,),
        )

    def delete_folder(
        self,
        credentials: BackgroundVaultCredentials,
        folder_path: str,
    ) -> DeleteFolderResult:
        credentials.password_bytes()

        return DeleteFolderResult(
            removed=(
                VaultEntrySummary(
                    name=f"{folder_path}/file.bin",
                    size=1,
                ),
            ),
            entries=(),
        )


class BlockingBackgroundBackend(FakeBackgroundBackend):
    """Hold an add operation until the test releases it."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def add_files(
        self,
        credentials: BackgroundVaultCredentials,
        source_paths: tuple[Path, ...],
        *,
        folder_path: str = "",
    ) -> AddFilesResult:
        credentials.password_bytes()
        self.started.set()

        if not self.release.wait(timeout=2):
            raise RuntimeError("test release timed out")

        return super().add_files(
            credentials,
            source_paths,
            folder_path=folder_path,
        )


def _session_guard() -> SessionGuard:
    return SessionGuard(
        probe=FakeKeyfileProbe(),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )


def _show_window(
    window: AsyncSecurityMainWindow,
) -> None:
    window.show()
    QApplication.processEvents()


def _activate_test_vault(
    window: AsyncSecurityMainWindow,
    tmp_path: Path,
) -> None:
    window._activate_vault(
        UnlockedVault.create(
            vault_path=(tmp_path / "Private.vault"),
            keyfile_path=(tmp_path / ".authkey"),
            password=("test password"),
        ),
        (),
    )
    QApplication.processEvents()


def test_background_add_updates_browser(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = AsyncSecurityMainWindow(
        backend=FakeVaultBackend(),
        background_backend=(FakeBackgroundBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_test_vault(
        window,
        tmp_path,
    )

    started = window.start_add_files((tmp_path / "large.bin",))

    assert started

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.vault_page.table.rowCount() == 1

    item = window.vault_page.table.item(0, 0)
    assert item is not None
    assert item.text() == "large.bin"
    assert window.statusBar().currentMessage() == "Added 1 file(s)."


def test_background_create_folder_updates_browser(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = AsyncSecurityMainWindow(
        backend=FakeVaultBackend(),
        background_backend=(FakeBackgroundBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_test_vault(
        window,
        tmp_path,
    )

    started = window.start_create_folder("Documents")

    assert started

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.vault_page.table.rowCount() == 1
    item = window.vault_page.table.item(0, 0)
    assert item is not None
    assert item.data(Qt.ItemDataRole.UserRole) == ("folder", "Documents")
    assert window.statusBar().currentMessage() == "Created folder Documents."


def test_background_delete_folder_updates_browser(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = AsyncSecurityMainWindow(
        backend=FakeVaultBackend(),
        background_backend=(FakeBackgroundBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_test_vault(
        window,
        tmp_path,
    )

    started = window.start_delete_folder("Documents")

    assert started

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert window.vault_page.table.rowCount() == 0
    assert (
        window.statusBar().currentMessage() == "Deleted folder Documents and 1 file."
    )


def test_start_add_files_targets_the_open_folder(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window = AsyncSecurityMainWindow(
        backend=FakeVaultBackend(),
        background_backend=(FakeBackgroundBackend()),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_test_vault(
        window,
        tmp_path,
    )

    window.vault_page.set_entries((VaultEntrySummary(name="Documents/.vaultkeep", size=0),))
    folder_item = window.vault_page.table.item(0, 0)
    window.vault_page.table.selectRow(0)
    window.vault_page._on_row_activated(folder_item)
    assert window.vault_page.current_folder == "Documents"

    started = window.start_add_files((tmp_path / "large.bin",))
    assert started

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    item = window.vault_page.table.item(0, 0)
    assert item is not None
    assert item.data(Qt.ItemDataRole.UserRole) == ("file", "Documents/large.bin")


def test_lock_during_task_discards_stale_ui_result(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    background_backend = BlockingBackgroundBackend()
    window = AsyncSecurityMainWindow(
        backend=FakeVaultBackend(),
        background_backend=(background_backend),
        session_guard=(_session_guard()),
    )
    qtbot.addWidget(window)
    _show_window(window)
    _activate_test_vault(
        window,
        tmp_path,
    )

    window.start_add_files((tmp_path / "large.bin",))

    qtbot.waitUntil(
        background_backend.started.is_set,
        timeout=2_000,
    )

    window.lock_vault()

    assert not window.is_unlocked
    assert window.current_page_name == "unlock"

    background_backend.release.set()

    qtbot.waitUntil(
        lambda: not window.is_busy,
        timeout=2_000,
    )

    assert not window.is_unlocked
    assert window.current_page_name == "unlock"
    assert window.vault_page.table.rowCount() == 0
