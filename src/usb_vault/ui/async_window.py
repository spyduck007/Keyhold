"""Responsive desktop window for long-running file operations."""

from __future__ import annotations

from collections.abc import (
    Sequence,
)
from pathlib import Path

from PySide6.QtGui import (
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QProgressBar,
)

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.background_backend import (
    AddFilesResult,
    BackgroundVaultBackend,
    BackgroundVaultCredentials,
    CoreBackgroundVaultBackend,
    DeleteFileResult,
)
from usb_vault.ui.components import FeedbackStatusBar
from usb_vault.ui.drop_support import (
    local_regular_file_paths,
)
from usb_vault.ui.main_window import (
    RecoveryPresenter,
)
from usb_vault.ui.recovery_backend import (
    VaultRecoveryBackend,
)
from usb_vault.ui.security_backend import (
    VaultSecurityBackend,
)
from usb_vault.ui.security_window import (
    SecurityMainWindow,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)
from usb_vault.ui.task_runner import (
    TaskFunction,
    TaskRunner,
    TaskSuccessHandler,
)


class AsyncSecurityMainWindow(SecurityMainWindow):
    """Run file encryption and extraction outside the GUI thread."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (SessionGuard | None) = None,
        recovery_backend: (VaultRecoveryBackend | None) = None,
        security_backend: (VaultSecurityBackend | None) = None,
        background_backend: (BackgroundVaultBackend | None) = None,
        task_runner: (TaskRunner | None) = None,
    ) -> None:
        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
            session_guard=session_guard,
            recovery_backend=(recovery_backend),
            security_backend=(security_backend),
        )

        self._background_backend = (
            background_backend if background_backend is not None else CoreBackgroundVaultBackend()
        )
        self._task_runner = task_runner if task_runner is not None else TaskRunner(parent=self)

        self._activity_indicator = QProgressBar()
        self._activity_indicator.setObjectName("backgroundActivityIndicator")
        self._activity_indicator.setRange(
            0,
            0,
        )
        self._activity_indicator.setTextVisible(False)
        self._activity_indicator.setFixedWidth(180)
        self._activity_indicator.hide()

        self.statusBar().addPermanentWidget(self._activity_indicator)

        self._task_runner.busy_changed.connect(self._on_busy_changed)

    @property
    def is_busy(self) -> bool:
        """Return whether a file operation is running."""
        return self._task_runner.is_busy

    @property
    def task_runner(self) -> TaskRunner:
        """Expose the runner for focused UI tests."""
        return self._task_runner

    def start_add_files(
        self,
        source_paths: Sequence[Path],
    ) -> bool:
        """Begin a sequential background import batch."""
        paths = tuple(Path(path) for path in source_paths)

        if not paths:
            return False

        if self.is_busy:
            self._show_busy_message()
            return False

        active_vault = self._require_vault()
        credentials = BackgroundVaultCredentials.from_unlocked(active_vault)

        def operation() -> object:
            return self._background_backend.add_files(
                credentials,
                paths,
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                AddFilesResult,
            ):
                self._show_task_protocol_error(active_vault)
                return

            if not self._is_current_vault(active_vault):
                return

            self.vault_page.set_entries(value.entries)
            self.statusBar().showMessage(
                _add_result_message(value),
                10_000,
            )

        return self._start_vault_task(
            active_vault=active_vault,
            credentials=credentials,
            operation=operation,
            succeeded=succeeded,
            status_message=(f"Adding {len(paths)} file(s)…"),
        )

    def start_extract_entry(
        self,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> bool:
        """Begin exporting one entry in the background."""
        if self.is_busy:
            self._show_busy_message()
            return False

        active_vault = self._require_vault()
        credentials = BackgroundVaultCredentials.from_unlocked(active_vault)
        destination = Path(destination_path)

        def operation() -> object:
            return self._background_backend.extract_file(
                credentials,
                stored_name,
                destination,
                overwrite=overwrite,
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                VaultEntrySummary,
            ):
                self._show_task_protocol_error(active_vault)
                return

            if not self._is_current_vault(active_vault):
                return

            self.statusBar().showMessage(
                (f"Exported {value.name} to {destination}."),
                10_000,
            )

        return self._start_vault_task(
            active_vault=active_vault,
            credentials=credentials,
            operation=operation,
            succeeded=succeeded,
            status_message=(f"Exporting {stored_name}…"),
        )

    def start_delete_entry(
        self,
        stored_name: str,
    ) -> bool:
        """Begin deleting one entry in the background."""
        if self.is_busy:
            self._show_busy_message()
            return False

        active_vault = self._require_vault()
        credentials = BackgroundVaultCredentials.from_unlocked(active_vault)

        def operation() -> object:
            return self._background_backend.delete_file(
                credentials,
                stored_name,
            )

        def succeeded(
            value: object,
        ) -> None:
            if not isinstance(
                value,
                DeleteFileResult,
            ):
                self._show_task_protocol_error(active_vault)
                return

            if not self._is_current_vault(active_vault):
                return

            self.vault_page.set_entries(value.entries)
            self.statusBar().showMessage(
                (f"Deleted {value.deleted.name}."),
                8_000,
            )

        return self._start_vault_task(
            active_vault=active_vault,
            credentials=credentials,
            operation=operation,
            succeeded=succeeded,
            status_message=(f"Deleting {stored_name}…"),
        )

    def dragEnterEvent(
        self,
        event: QDragEnterEvent,
    ) -> None:
        """Accept dropped files only when no operation is active."""
        paths = local_regular_file_paths(event.mimeData())

        if self.is_unlocked and not self.is_busy and paths:
            event.acceptProposedAction()
            return

        event.ignore()

    def dragMoveEvent(
        self,
        event: QDragMoveEvent,
    ) -> None:
        """Continue accepting a valid idle-state drag."""
        paths = local_regular_file_paths(event.mimeData())

        if self.is_unlocked and not self.is_busy and paths:
            event.acceptProposedAction()
            return

        event.ignore()

    def dropEvent(
        self,
        event: QDropEvent,
    ) -> None:
        """Begin background encryption for dropped files."""
        paths = local_regular_file_paths(event.mimeData())

        if not self.is_unlocked or self.is_busy or not paths:
            event.ignore()
            return

        event.acceptProposedAction()
        self.start_add_files(paths)

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Keep the process alive while an atomic operation finishes."""
        if self.is_busy:
            self.statusBar().showMessage(
                ("A vault operation is still in progress."),
                8_000,
            )
            event.ignore()
            return

        super().closeEvent(event)

    def _on_add_requested(self) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add files to vault",
        )

        if selected_paths:
            self.start_add_files(tuple(Path(path) for path in selected_paths))

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

        self.start_extract_entry(
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
            self.start_delete_entry(stored_name)

    def _start_vault_task(
        self,
        *,
        active_vault: UnlockedVault,
        credentials: BackgroundVaultCredentials,
        operation: TaskFunction,
        succeeded: TaskSuccessHandler,
        status_message: str,
    ) -> bool:
        self.statusBar().showMessage(status_message)

        def guarded_operation() -> object:
            try:
                return operation()
            finally:
                credentials.close()

        def failed(
            message: str,
        ) -> None:
            if self._is_current_vault(active_vault):
                self._show_status_error(message)

        try:
            self._task_runner.start(
                guarded_operation,
                succeeded=succeeded,
                failed=failed,
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            credentials.close()
            self._show_status_error(str(error))
            return False

        return True

    def _is_current_vault(
        self,
        vault: UnlockedVault,
    ) -> bool:
        return self._vault is vault and self.is_unlocked

    def _show_task_protocol_error(
        self,
        active_vault: UnlockedVault,
    ) -> None:
        if self._is_current_vault(active_vault):
            self._show_status_error("Background operation returned an invalid result.")

    def _show_busy_message(self) -> None:
        self.statusBar().showMessage(
            ("Another vault operation is already in progress."),
            8_000,
        )

    def _on_busy_changed(
        self,
        busy: bool,
    ) -> None:
        self._pages.setEnabled(not busy)
        self._activity_indicator.setVisible(busy)
        status_bar = self.statusBar()
        if isinstance(status_bar, FeedbackStatusBar):
            status_bar.set_busy(busy)

        self.new_vault_action.setEnabled(not busy)
        self.recover_access_action.setEnabled(not busy)
        self.security_action.setEnabled(not busy and self.is_unlocked)

        # Manual locking remains available from the File menu.
        self.lock_action.setEnabled(self.is_unlocked)


def _add_result_message(
    result: AddFilesResult,
) -> str:
    if not result.failures:
        return f"Added {len(result.added)} file(s)."

    first_failure = result.failures[0]

    if not result.added and len(result.failures) == 1:
        return f"{first_failure.path.name}: {first_failure.message}"

    return (
        f"Added {len(result.added)} file(s); "
        f"{len(result.failures)} failed. "
        "First failure: "
        f"{first_failure.path.name}: "
        f"{first_failure.message}"
    )
