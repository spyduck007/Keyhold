"""Desktop window with a card-based vault-library home screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)

from usb_vault.platform.macos.usb_discovery import (
    UsbKeyLocator,
)
from usb_vault.ui.backend import (
    VaultBackend,
)
from usb_vault.ui.background_backend import (
    BackgroundVaultBackend,
)
from usb_vault.ui.main_window import (
    RecoveryPresenter,
)
from usb_vault.ui.pages.vault_library_page import (
    VaultLibraryPage,
)
from usb_vault.ui.recovery_backend import (
    VaultRecoveryBackend,
)
from usb_vault.ui.rename_backend import (
    RenameVaultBackend,
)
from usb_vault.ui.security_backend import (
    VaultSecurityBackend,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)
from usb_vault.ui.task_runner import (
    TaskRunner,
)
from usb_vault.ui.usb_grace import (
    UsbGraceSessionGuard,
)
from usb_vault.ui.vault_library import (
    VaultLibraryEntry,
    VaultLibraryError,
    VaultLibraryStore,
)
from usb_vault.ui.vault_library_window import (
    VaultLibraryMainWindow,
)


class VaultCardsMainWindow(VaultLibraryMainWindow):
    """Use the persistent vault registry as the locked-state home."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (UsbGraceSessionGuard | None) = None,
        recovery_backend: (VaultRecoveryBackend | None) = None,
        security_backend: (VaultSecurityBackend | None) = None,
        background_backend: (BackgroundVaultBackend | None) = None,
        task_runner: (TaskRunner | None) = None,
        rename_backend: (RenameVaultBackend | None) = None,
        key_locator: (UsbKeyLocator | None) = None,
        vault_library: (VaultLibraryStore | None) = None,
    ) -> None:
        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=session_guard,
            recovery_backend=(recovery_backend),
            security_backend=(security_backend),
            background_backend=(background_backend),
            task_runner=task_runner,
            rename_backend=(rename_backend),
            key_locator=key_locator,
            vault_library=(vault_library),
        )

        self.library_page = VaultLibraryPage()
        self._pages.insertWidget(
            0,
            self.library_page,
        )

        self.library_page.create_requested.connect(self.show_setup_page)
        self.library_page.add_existing_requested.connect(self._on_add_existing_requested)
        self.library_page.refresh_requested.connect(self._on_library_refresh_requested)
        self.library_page.open_requested.connect(self._on_library_open_requested)
        self.library_page.rename_requested.connect(self._on_library_rename_requested)
        self.library_page.remove_requested.connect(self._on_library_remove_requested)

        self.show_library_page()

    @property
    def current_page_name(self) -> str:
        """Return a stable page name for navigation tests."""
        if (
            hasattr(
                self,
                "library_page",
            )
            and self._pages.currentWidget() is self.library_page
        ):
            return "library"

        return super().current_page_name

    def show_library_page(self) -> None:
        """Show the current card library."""
        if self.is_unlocked:
            self.lock_vault()
            return

        self._refresh_library()
        self._pages.setCurrentWidget(self.library_page)
        self.statusBar().showMessage(
            "Choose a vault to unlock.",
            5_000,
        )

    def _show_unlock_page(self) -> None:
        """Return locked navigation to the vault library."""
        # MainWindow invokes this during its own constructor, before
        # the card page has been created.
        if not hasattr(
            self,
            "library_page",
        ):
            super()._show_unlock_page()
            return

        self.show_library_page()

    def _on_library_open_requested(
        self,
        vault_id: bytes,
    ) -> None:
        entry = self._find_library_entry(vault_id)

        if entry is None:
            return

        if not entry.is_available:
            self.library_page.show_error(
                "The encrypted vault file "
                "could not be found. Use "
                "Add Existing Vault to locate "
                "it again, or remove this card."
            )
            return

        self._show_unlock_form(
            entry.vault_path,
            display_name=(entry.display_name),
        )

    def _on_add_existing_requested(
        self,
    ) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add existing encrypted vault",
            "",
            ("USB Vault files (*.vault);;All files (*)"),
        )

        if not selected_path:
            return

        selected_vault = Path(selected_path)

        self._show_unlock_form(
            selected_vault,
            display_name=(selected_vault.stem or "Vault"),
        )

    def _on_library_refresh_requested(
        self,
    ) -> None:
        if self._refresh_library():
            self.statusBar().showMessage(
                "Vault library refreshed.",
                5_000,
            )

    def _on_library_rename_requested(
        self,
        vault_id: bytes,
    ) -> None:
        entry = self._find_library_entry(vault_id)

        if entry is None:
            return

        display_name, accepted = QInputDialog.getText(
            self,
            "Rename vault card",
            "Display name:",
            QLineEdit.EchoMode.Normal,
            entry.display_name,
        )

        if not accepted:
            return

        try:
            renamed = self.vault_library.rename_vault(
                vault_id,
                display_name,
            )
        except (
            OSError,
            ValueError,
            VaultLibraryError,
        ) as error:
            self.library_page.show_error(str(error))
            return

        self._refresh_library()
        self.statusBar().showMessage(
            (f"Vault card renamed to {renamed.display_name}."),
            5_000,
        )

    def _on_library_remove_requested(
        self,
        vault_id: bytes,
    ) -> None:
        entry = self._find_library_entry(vault_id)

        if entry is None:
            return

        answer = QMessageBox.question(
            self,
            "Remove vault card?",
            (
                f"Remove {entry.display_name} "
                "from this app?\n\n"
                "The encrypted vault file will "
                "not be deleted."
            ),
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            removed = self.vault_library.remove_vault(vault_id)
        except (
            OSError,
            ValueError,
            VaultLibraryError,
        ) as error:
            self.library_page.show_error(str(error))
            return

        if not removed:
            self.library_page.show_error("Vault card was not found.")
            return

        self._refresh_library()
        self.statusBar().showMessage(
            (f"Removed {entry.display_name} from the app. The vault file was not deleted."),
            8_000,
        )

    def _show_unlock_form(
        self,
        vault_path: Path,
        *,
        display_name: str,
    ) -> None:
        self.unlock_page.clear_password()
        self.unlock_page.clear_error()

        self.unlock_page.vault_path_edit.setText(str(vault_path))
        self.unlock_page.keyfile_path_edit.clear()

        self._pages.setCurrentWidget(self.unlock_page)
        self.unlock_page.password_edit.setFocus()

        self.statusBar().showMessage(
            (
                f"Enter the password for "
                f"{display_name}. "
                "A registered USB key will "
                "be detected automatically."
            )
        )

    def _find_library_entry(
        self,
        vault_id: bytes,
    ) -> VaultLibraryEntry | None:
        try:
            entry = self.vault_library.find_vault(vault_id)
        except (
            OSError,
            ValueError,
            VaultLibraryError,
        ) as error:
            self.library_page.show_error(str(error))
            return None

        if entry is None:
            self.library_page.show_error("Vault card was not found.")
            return None

        return entry

    def _refresh_library(
        self,
    ) -> bool:
        try:
            entries = self.vault_library.list_entries()
        except (
            OSError,
            ValueError,
            VaultLibraryError,
        ) as error:
            self.library_page.show_error(str(error))
            return False

        self.library_page.set_entries(entries)
        self.library_page.clear_error()
        return True
