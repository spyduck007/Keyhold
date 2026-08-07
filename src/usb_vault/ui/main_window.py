"""Main desktop window for creating, opening, and browsing vaults."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.platform.macos.usb_ejection import MacOsSessionUsbEjector
from usb_vault.ui.animated_stack import AnimatedStackedWidget
from usb_vault.ui.backend import (
    CoreVaultBackend,
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.components import FeedbackStatusBar
from usb_vault.ui.drop_support import (
    local_regular_file_paths,
)
from usb_vault.ui.icons import app_icon
from usb_vault.ui.pages.setup_page import (
    SetupPage,
)
from usb_vault.ui.pages.unlock_page import (
    UnlockPage,
)
from usb_vault.ui.pages.vault_page import (
    VaultPage,
)
from usb_vault.ui.recovery_dialog import (
    show_recovery_code,
)
from usb_vault.ui.setup_backend import (
    CoreVaultSetupBackend,
    VaultSetupBackend,
)

RecoveryPresenter = Callable[
    [
        QWidget,
        str,
    ],
    None,
]


class MainWindow(QMainWindow):
    """Coordinate setup, locked, and unlocked desktop views."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        usb_ejector: MacOsSessionUsbEjector | None = None,
    ) -> None:
        super().__init__()

        self.setObjectName("mainWindow")
        self.setWindowTitle("USB Vault")
        self.setWindowIcon(app_icon("shield", "#61d7c5"))
        self.resize(980, 680)
        self.setMinimumSize(760, 520)
        self.setAcceptDrops(True)
        self.setStatusBar(FeedbackStatusBar(self))

        self._backend = backend if backend is not None else CoreVaultBackend()
        self._setup_backend = (
            setup_backend if setup_backend is not None else CoreVaultSetupBackend()
        )
        self._recovery_presenter = (
            recovery_presenter if recovery_presenter is not None else show_recovery_code
        )
        self._vault: UnlockedVault | None = None
        self._usb_ejector = usb_ejector if usb_ejector is not None else MacOsSessionUsbEjector()

        self.unlock_page = UnlockPage()
        self.setup_page = SetupPage()
        self.vault_page = VaultPage()

        self._pages = AnimatedStackedWidget()
        self._pages.addWidget(self.unlock_page)
        self._pages.addWidget(self.setup_page)
        self._pages.addWidget(self.vault_page)
        self.setCentralWidget(self._pages)

        self._create_actions()
        self._create_menu()

        self.unlock_page.unlock_requested.connect(self._on_unlock_requested)
        self.setup_page.setup_requested.connect(self._on_setup_requested)
        self.setup_page.cancel_requested.connect(self._show_unlock_page)
        self.vault_page.add_requested.connect(self._on_add_requested)
        self.vault_page.extract_requested.connect(self._on_extract_requested)
        self.vault_page.delete_requested.connect(self._on_delete_requested)
        self.vault_page.lock_requested.connect(self.lock_vault)

        self._show_unlock_page()

    @property
    def is_unlocked(self) -> bool:
        """Return whether the window has active credentials."""
        return self._vault is not None and not self._vault.is_closed

    @property
    def current_page_name(self) -> str:
        """Return a stable page name for tests and navigation."""
        current_widget = self._pages.currentWidget()

        if current_widget is self.vault_page:
            return "vault"

        if current_widget is self.setup_page:
            return "setup"

        return "unlock"

    def show_setup_page(self) -> None:
        """Open a clean new-vault setup form."""
        if self.is_unlocked:
            self.lock_vault()

        self.setup_page.reset()
        self.setup_page.refresh_usb_volumes()
        self._pages.setCurrentWidget(self.setup_page)
        self.statusBar().showMessage(
            "Create a new encrypted vault.",
            5_000,
        )

    def refresh_entries(self) -> bool:
        """Reload decrypted metadata from the vault."""
        try:
            vault = self._require_vault()
            entries = self._backend.list_entries(vault)
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self._show_status_error(str(error))
            return False

        self.vault_page.set_entries(entries)
        return True

    def add_file_from_path(
        self,
        source_path: Path,
    ) -> bool:
        """Add a selected source file and refresh the browser."""
        try:
            vault = self._require_vault()
            result = self._backend.add_file(
                vault,
                source_path,
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self._show_status_error(str(error))
            return False

        if not self.refresh_entries():
            return False

        self.statusBar().showMessage(
            f"Added {result.name}.",
            5_000,
        )
        return True

    def add_files_from_paths(
        self,
        source_paths: Sequence[Path],
    ) -> tuple[int, int]:
        """Add multiple selected or dropped files."""
        added_count = 0
        failed_count = 0

        for source_path in source_paths:
            if self.add_file_from_path(source_path):
                added_count += 1
            else:
                failed_count += 1

        if failed_count and (added_count > 0 or failed_count > 1):
            self.statusBar().showMessage(
                (f"Added {added_count} file(s); {failed_count} failed."),
                8_000,
            )
        elif not failed_count:
            self.statusBar().showMessage(
                (f"Added {added_count} file(s)."),
                5_000,
            )

        return (
            added_count,
            failed_count,
        )

    def extract_entry_to(
        self,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> bool:
        """Extract one selected entry."""
        try:
            vault = self._require_vault()
            result = self._backend.extract_file(
                vault,
                stored_name,
                destination_path,
                overwrite=overwrite,
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self._show_status_error(str(error))
            return False

        self.statusBar().showMessage(
            (f"Exported {result.name} to {destination_path}."),
            8_000,
        )
        return True

    def delete_entry(
        self,
        stored_name: str,
    ) -> bool:
        """Delete one selected vault entry."""
        try:
            vault = self._require_vault()
            result = self._backend.delete_file(
                vault,
                stored_name,
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self._show_status_error(str(error))
            return False

        if not self.refresh_entries():
            return False

        self.statusBar().showMessage(
            f"Deleted {result.name}.",
            5_000,
        )
        return True

    def lock_vault(self) -> None:
        """Clear credentials and return to the locked screen."""
        if self._vault is not None:
            self._vault.close()
            self._vault = None

        self.vault_page.clear_entries()
        self.unlock_page.reset_after_lock()
        self.lock_action.setEnabled(False)
        self._show_unlock_page()

        self.statusBar().showMessage(
            "Vault locked.",
            5_000,
        )

    def dragEnterEvent(
        self,
        event: QDragEnterEvent,
    ) -> None:
        """Accept local regular files while the vault is unlocked."""
        paths = local_regular_file_paths(event.mimeData())

        if self.is_unlocked and paths:
            event.acceptProposedAction()
            return

        event.ignore()

    def dragMoveEvent(
        self,
        event: QDragMoveEvent,
    ) -> None:
        """Continue accepting valid file drags."""
        paths = local_regular_file_paths(event.mimeData())

        if self.is_unlocked and paths:
            event.acceptProposedAction()
            return

        event.ignore()

    def dropEvent(
        self,
        event: QDropEvent,
    ) -> None:
        """Encrypt dropped local files into the open vault."""
        paths = local_regular_file_paths(event.mimeData())

        if not self.is_unlocked or not paths:
            event.ignore()
            return

        event.acceptProposedAction()
        self.add_files_from_paths(paths)

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Clear UI session credentials before closing."""
        self.lock_vault()
        self._usb_ejector.eject_accessed_volumes()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        self.new_vault_action = QAction(
            "New Vault…",
            self,
        )
        self.new_vault_action.setObjectName("newVaultAction")
        self.new_vault_action.setIcon(app_icon("plus"))
        self.new_vault_action.setShortcut("Ctrl+N")
        self.new_vault_action.triggered.connect(self.show_setup_page)

        self.lock_action = QAction(
            "Lock Vault",
            self,
        )
        self.lock_action.setObjectName("lockVaultAction")
        self.lock_action.setIcon(app_icon("lock"))
        self.lock_action.setShortcut("Ctrl+L")
        self.lock_action.setEnabled(False)
        self.lock_action.triggered.connect(self.lock_vault)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_vault_action)
        file_menu.addSeparator()
        file_menu.addAction(self.lock_action)

    def _on_setup_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
        self._usb_ejector.record_keyfile_path(Path(keyfile_path))

        try:
            created = self._setup_backend.create_vault(
                vault_path=Path(vault_path),
                keyfile_path=Path(keyfile_path),
                password=password,
            )
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            self.setup_page.clear_sensitive_fields()
            self.setup_page.show_error(str(error))
            self.statusBar().showMessage(
                "Vault creation failed.",
                8_000,
            )
            return

        self.setup_page.clear_sensitive_fields()

        self.unlock_page.vault_path_edit.setText(str(created.vault.vault_path))
        self.unlock_page.keyfile_path_edit.setText(str(created.vault.keyfile_path))

        self._recovery_presenter(
            self,
            created.recovery_code,
        )
        self._activate_vault(
            created.vault,
            created.entries,
        )

        self.statusBar().showMessage(
            "Vault created and unlocked.",
            8_000,
        )

    def _on_unlock_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
        self._usb_ejector.record_keyfile_path(Path(keyfile_path))
        candidate: UnlockedVault | None = None

        try:
            candidate = UnlockedVault.create(
                vault_path=vault_path,
                keyfile_path=(keyfile_path),
                password=password,
            )
            entries = self._backend.unlock(candidate)
        except (
            VaultError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            if candidate is not None:
                candidate.close()

            self.unlock_page.show_error(str(error))
            self.statusBar().showMessage(
                "Unlock failed.",
                5_000,
            )
            return

        self.unlock_page.clear_password()
        self._activate_vault(
            candidate,
            entries,
        )

        self.statusBar().showMessage(
            "Vault unlocked.",
            5_000,
        )

    def _activate_vault(
        self,
        vault: UnlockedVault,
        entries: Sequence[VaultEntrySummary],
    ) -> None:
        if self._vault is not None:
            self._vault.close()

        self._vault = vault
        self._usb_ejector.record_keyfile_path(vault.keyfile_path)
        self.vault_page.set_vault_path(str(vault.vault_path))
        self.vault_page.set_entries(entries)
        self.lock_action.setEnabled(True)
        self._pages.setCurrentWidget(self.vault_page)

    def _on_add_requested(self) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add files to vault",
        )

        if selected_paths:
            self.add_files_from_paths(tuple(Path(path) for path in selected_paths))

    def _on_extract_requested(
        self,
        stored_name: str,
    ) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export file from vault",
            stored_name,
        )

        if not selected_path:
            return

        destination = Path(selected_path)
        overwrite = False

        if destination.exists():
            answer = QMessageBox.question(
                self,
                "Replace existing file?",
                (f"{destination.name} already exists. Replace it?"),
                (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

            overwrite = True

        self.extract_entry_to(
            stored_name,
            destination,
            overwrite=overwrite,
        )

    def _on_delete_requested(
        self,
        stored_name: str,
    ) -> None:
        answer = QMessageBox.question(
            self,
            "Delete encrypted file?",
            (f"Delete {stored_name} from the vault?"),
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.delete_entry(stored_name)

    def _show_unlock_page(self) -> None:
        self._pages.setCurrentWidget(self.unlock_page)

    def _require_vault(
        self,
    ) -> UnlockedVault:
        if self._vault is None:
            raise RuntimeError("vault is locked")

        return self._vault

    def _show_status_error(
        self,
        message: str,
    ) -> None:
        self.statusBar().showMessage(
            message,
            8_000,
        )

    def _record_additional_usb_keyfiles(self, keyfile_paths: Sequence[Path]) -> None:
        """Remember extra USB keys used by a security-management workflow."""
        self._usb_ejector.record_keyfile_paths(keyfile_paths)
