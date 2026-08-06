"""Desktop window with automatic USB and inactivity locking."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import (
    QCloseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.backend import (
    UnlockedVault,
    VaultBackend,
)
from usb_vault.ui.main_window import (
    MainWindow,
    RecoveryPresenter,
)
from usb_vault.ui.session_guard import (
    SessionGuard,
    UserActivityFilter,
)
from usb_vault.ui.setup_backend import (
    VaultSetupBackend,
)


class MonitoredMainWindow(MainWindow):
    """Add automatic session locking to the normal desktop window."""

    def __init__(
        self,
        *,
        backend: VaultBackend | None = None,
        setup_backend: (VaultSetupBackend | None) = None,
        recovery_presenter: (RecoveryPresenter | None) = None,
        session_guard: (SessionGuard | None) = None,
    ) -> None:
        super().__init__(
            backend=backend,
            setup_backend=setup_backend,
            recovery_presenter=(recovery_presenter),
        )

        self._session_guard = (
            session_guard if session_guard is not None else SessionGuard(parent=self)
        )
        self._activity_filter = UserActivityFilter(self)
        self._activity_filter_installed = False

        self._session_guard.usb_key_unavailable.connect(self._lock_after_usb_loss)
        self._session_guard.idle_timeout.connect(self._lock_after_idle_timeout)
        self._activity_filter.activity.connect(self._session_guard.reset_idle_timer)

        self._install_activity_filter()

    @property
    def session_guard(self) -> SessionGuard:
        """Return the active monitoring component."""
        return self._session_guard

    def lock_vault(self) -> None:
        """Stop monitoring and perform the normal manual lock."""
        self._session_guard.stop()
        super().lock_vault()

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Remove global activity monitoring before closing."""
        self._remove_activity_filter()
        super().closeEvent(event)

    def _activate_vault(
        self,
        vault: UnlockedVault,
        entries: Sequence[VaultEntrySummary],
    ) -> None:
        super()._activate_vault(
            vault,
            entries,
        )
        self._session_guard.start(vault.keyfile_path)

        self.statusBar().showMessage(
            ("Vault unlocked. Automatic locking is active."),
            5_000,
        )

    def _lock_after_usb_loss(self) -> None:
        self._lock_with_message(("USB keyfile removed, changed, or unavailable. Vault locked."))

    def _lock_after_idle_timeout(
        self,
    ) -> None:
        self._lock_with_message(("Vault locked after the inactivity timeout."))

    def _lock_with_message(
        self,
        message: str,
    ) -> None:
        if not self.is_unlocked:
            return

        self.lock_vault()
        self.statusBar().showMessage(
            message,
            10_000,
        )

    def _install_activity_filter(
        self,
    ) -> None:
        application = QApplication.instance()

        if not isinstance(
            application,
            QApplication,
        ):
            raise RuntimeError("a QApplication must exist before creating the window")

        application.installEventFilter(self._activity_filter)
        self._activity_filter_installed = True

    def _remove_activity_filter(
        self,
    ) -> None:
        if not self._activity_filter_installed:
            return

        application = QApplication.instance()

        if isinstance(
            application,
            QApplication,
        ):
            application.removeEventFilter(self._activity_filter)

        self._activity_filter_installed = False
