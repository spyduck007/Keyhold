"""Main desktop window for opening and browsing a vault."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.ui.backend import (
    CoreVaultBackend,
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.pages.unlock_page import (
    UnlockPage,
)
from usb_vault.ui.pages.vault_page import (
    VaultPage,
)


class MainWindow(QMainWindow):
    """Coordinate the locked and unlocked desktop views."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
    ) -> None:
        super().__init__()

        self.setObjectName("mainWindow")
        self.setWindowTitle("USB Vault")
        self.resize(
            780,
            520,
        )

        self._backend = backend if backend is not None else CoreVaultBackend()
        self._vault: UnlockedVault | None = None

        self.unlock_page = UnlockPage()
        self.vault_page = VaultPage()

        self._pages = QStackedWidget()
        self._pages.addWidget(self.unlock_page)
        self._pages.addWidget(self.vault_page)
        self.setCentralWidget(self._pages)

        self.unlock_page.unlock_requested.connect(self._on_unlock_requested)
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

        return "unlock"

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
        self._show_unlock_page()

        self.statusBar().showMessage(
            "Vault locked.",
            5_000,
        )

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Clear UI session credentials before closing."""
        self.lock_vault()
        super().closeEvent(event)

    def _on_unlock_requested(
        self,
        vault_path: str,
        keyfile_path: str,
        password: str,
    ) -> None:
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

        if self._vault is not None:
            self._vault.close()

        self._vault = candidate
        self.unlock_page.clear_password()
        self.vault_page.set_vault_path(vault_path)
        self.vault_page.set_entries(entries)
        self._pages.setCurrentWidget(self.vault_page)

        self.statusBar().showMessage(
            "Vault unlocked.",
            5_000,
        )

    def _on_add_requested(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add file to vault",
        )

        if selected_path:
            self.add_file_from_path(Path(selected_path))

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
