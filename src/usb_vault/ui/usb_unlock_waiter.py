"""Background polling for a registered mounted USB key."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QTimer,
    Signal,
)

from usb_vault.platform.macos.usb_discovery import (
    UsbKeyLocator,
)
from usb_vault.ui.task_runner import (
    TaskRunner,
)

DEFAULT_USB_UNLOCK_POLL_INTERVAL_MS = 750


class UsbUnlockWaiter(QObject):
    """Poll for a registered USB key without blocking the GUI thread."""

    keyfile_found = Signal(object)
    scan_failed = Signal(str)

    def __init__(
        self,
        *,
        locator: UsbKeyLocator,
        poll_interval_ms: int = DEFAULT_USB_UNLOCK_POLL_INTERVAL_MS,
        task_runner: TaskRunner | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        _require_positive_integer(
            "poll_interval_ms",
            poll_interval_ms,
        )

        self._locator = locator
        self._poll_interval_ms = poll_interval_ms
        self._task_runner = task_runner if task_runner is not None else TaskRunner(parent=self)

        self._vault_path: Path | None = None
        self._active = False
        self._generation = 0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._poll_interval_ms)
        self._timer.timeout.connect(self._scan_now)

    @property
    def is_active(self) -> bool:
        """Return whether the waiter is looking for a USB key."""
        return self._active

    @property
    def vault_path(self) -> Path | None:
        """Return the vault currently being monitored."""
        return self._vault_path

    def start(
        self,
        vault_path: str | Path,
    ) -> None:
        """Begin polling for a key registered to one vault."""
        self.cancel()

        self._generation += 1
        self._vault_path = Path(vault_path)
        self._active = True

        self._scan_now()

    def cancel(self) -> None:
        """Stop polling and invalidate any in-flight scan result."""
        self._generation += 1
        self._timer.stop()
        self._vault_path = None
        self._active = False

    def _scan_now(self) -> None:
        if not self._active or self._vault_path is None:
            return

        if self._task_runner.is_busy:
            self._timer.start(self._poll_interval_ms)
            return

        generation = self._generation
        vault_path = self._vault_path

        def operation() -> object:
            return self._locator.find_matching_keyfile(vault_path)

        def succeeded(
            value: object,
        ) -> None:
            if not self._is_current(generation):
                return

            if value is None:
                self._timer.start(self._poll_interval_ms)
                return

            if not isinstance(
                value,
                Path,
            ):
                self._fail_current(
                    generation,
                    ("USB key detection returned an invalid result."),
                )
                return

            self._timer.stop()
            self._active = False
            self._vault_path = None

            self.keyfile_found.emit(value)

        def failed(
            message: str,
        ) -> None:
            self._fail_current(
                generation,
                message,
            )

        try:
            self._task_runner.start(
                operation,
                succeeded=succeeded,
                failed=failed,
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            self._fail_current(
                generation,
                str(error),
            )

    def _fail_current(
        self,
        generation: int,
        message: str,
    ) -> None:
        if not self._is_current(generation):
            return

        normalized_message = message.strip()

        if not normalized_message:
            normalized_message = "Unable to scan for registered USB keys."

        self._timer.stop()
        self._active = False
        self._vault_path = None

        self.scan_failed.emit(normalized_message)

    def _is_current(
        self,
        generation: int,
    ) -> bool:
        return self._active and generation == self._generation


def _require_positive_integer(
    name: str,
    value: int,
) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
