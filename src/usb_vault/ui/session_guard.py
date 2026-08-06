"""USB-presence and idle-timeout monitoring for unlocked UI sessions."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import (
    QEvent,
    QObject,
    QTimer,
    Signal,
)

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.core.storage.reader import (
    read_usb_keyfile,
)

DEFAULT_USB_POLL_INTERVAL_MS = 1_000
DEFAULT_IDLE_TIMEOUT_MS = 300_000


class KeyfileIdentityProbe(Protocol):
    """Read the non-secret identifier from a USB keyfile."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        """Return the key ID, or None when unavailable or invalid."""


class CoreKeyfileIdentityProbe:
    """Production keyfile identity probe."""

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        """Read a validated keyfile and return its public identifier."""
        try:
            return read_usb_keyfile(keyfile_path).key_id
        except (
            VaultError,
            OSError,
            ValueError,
        ):
            return None


class SessionGuard(QObject):
    """Monitor the active USB identity and user inactivity."""

    usb_key_unavailable = Signal()
    idle_timeout = Signal()

    def __init__(
        self,
        *,
        probe: KeyfileIdentityProbe | None = None,
        usb_poll_interval_ms: int = (DEFAULT_USB_POLL_INTERVAL_MS),
        idle_timeout_ms: int = (DEFAULT_IDLE_TIMEOUT_MS),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        _require_positive_integer(
            "usb_poll_interval_ms",
            usb_poll_interval_ms,
        )
        _require_positive_integer(
            "idle_timeout_ms",
            idle_timeout_ms,
        )

        self._probe = probe if probe is not None else CoreKeyfileIdentityProbe()
        self._usb_poll_interval_ms = usb_poll_interval_ms
        self._idle_timeout_ms = idle_timeout_ms

        self._keyfile_path: Path | None = None
        self._expected_key_id: bytes | None = None
        self._active = False

        self._usb_timer = QTimer(self)
        self._usb_timer.setInterval(self._usb_poll_interval_ms)
        self._usb_timer.timeout.connect(self.check_keyfile_now)

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._emit_idle_timeout)

    @property
    def is_active(self) -> bool:
        """Return whether monitoring is active."""
        return self._active

    @property
    def keyfile_path(self) -> Path | None:
        """Return the keyfile currently being monitored."""
        return self._keyfile_path

    def start(
        self,
        keyfile_path: str | Path,
    ) -> None:
        """Begin monitoring one exact USB keyfile identity."""
        self.stop()

        path = Path(keyfile_path)
        expected_key_id = self._probe.read_key_id(path)

        self._keyfile_path = path
        self._expected_key_id = expected_key_id
        self._active = True

        if expected_key_id is None:
            QTimer.singleShot(
                0,
                self._emit_usb_key_unavailable,
            )
            return

        self._usb_timer.start()
        self._idle_timer.start(self._idle_timeout_ms)

    def stop(self) -> None:
        """Stop all monitoring and clear captured identity state."""
        self._usb_timer.stop()
        self._idle_timer.stop()

        self._keyfile_path = None
        self._expected_key_id = None
        self._active = False

    def reset_idle_timer(self) -> None:
        """Restart the inactivity countdown after user activity."""
        if not self._active or self._expected_key_id is None:
            return

        self._idle_timer.start(self._idle_timeout_ms)

    def check_keyfile_now(self) -> None:
        """Immediately verify the monitored keyfile identity."""
        if not self._active:
            return

        if self._keyfile_path is None or self._expected_key_id is None:
            self._emit_usb_key_unavailable()
            return

        current_key_id = self._probe.read_key_id(self._keyfile_path)

        if current_key_id is None or not hmac.compare_digest(
            current_key_id,
            self._expected_key_id,
        ):
            self._emit_usb_key_unavailable()

    def _emit_usb_key_unavailable(
        self,
    ) -> None:
        if not self._active:
            return

        self.stop()
        self.usb_key_unavailable.emit()

    def _emit_idle_timeout(self) -> None:
        if not self._active:
            return

        self.stop()
        self.idle_timeout.emit()


class UserActivityFilter(QObject):
    """Emit a signal for intentional user-input events."""

    activity = Signal()

    _ACTIVITY_TYPES = frozenset(
        {
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
        }
    )

    def eventFilter(
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        """Observe activity without consuming the event."""
        del watched

        if event.type() in self._ACTIVITY_TYPES:
            self.activity.emit()

        return False


def _require_positive_integer(
    name: str,
    value: int,
) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
