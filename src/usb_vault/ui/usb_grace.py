"""USB-key reconnection grace period for unlocked sessions."""

from __future__ import annotations

import hmac
from pathlib import Path

from PySide6.QtCore import (
    QTimer,
    Signal,
)

from usb_vault.ui.session_guard import (
    SessionGuard,
)

DEFAULT_USB_RECONNECT_GRACE_MS = 5_000


class UsbGraceSessionGuard(SessionGuard):
    """Delay automatic locking while the same USB key is reinserted."""

    usb_key_grace_started = Signal(int)
    usb_key_restored = Signal()

    def __init__(
        self,
        *,
        usb_reconnect_grace_ms: int = (DEFAULT_USB_RECONNECT_GRACE_MS),
        **kwargs: object,
    ) -> None:
        _require_positive_integer(
            "usb_reconnect_grace_ms",
            usb_reconnect_grace_ms,
        )

        super().__init__(**kwargs)

        self._usb_reconnect_grace_ms = usb_reconnect_grace_ms
        self._usb_grace_active = False

        self._usb_grace_timer = QTimer(self)
        self._usb_grace_timer.setSingleShot(True)
        self._usb_grace_timer.setInterval(self._usb_reconnect_grace_ms)
        self._usb_grace_timer.timeout.connect(self._expire_usb_grace)

    @property
    def is_in_usb_grace(self) -> bool:
        """Return whether the USB is currently considered missing."""
        return self._usb_grace_active

    @property
    def usb_reconnect_grace_ms(
        self,
    ) -> int:
        """Return the configured USB reconnection period."""
        return self._usb_reconnect_grace_ms

    def start(
        self,
        keyfile_path: str | Path,
    ) -> None:
        """Begin normal monitoring with no pending grace period."""
        self._cancel_usb_grace(
            restart_idle_timer=False,
            emit_restored=False,
        )
        super().start(keyfile_path)

    def stop(self) -> None:
        """Stop monitoring and cancel a pending grace period."""
        self._usb_grace_timer.stop()
        self._usb_grace_active = False
        super().stop()

    def reset_idle_timer(self) -> None:
        """Ignore activity while the required USB key is unavailable."""
        if self._usb_grace_active:
            return

        super().reset_idle_timer()

    def check_keyfile_now(self) -> None:
        """Verify the key, starting or cancelling grace as needed."""
        if not self._active:
            return

        if self._keyfile_path is None or self._expected_key_id is None:
            self._emit_usb_key_unavailable()
            return

        current_key_id = self._probe.read_key_id(self._keyfile_path)

        key_matches = current_key_id is not None and hmac.compare_digest(
            current_key_id,
            self._expected_key_id,
        )

        if key_matches:
            if self._usb_grace_active:
                self._cancel_usb_grace(
                    restart_idle_timer=True,
                    emit_restored=True,
                )

            return

        if not self._usb_grace_active:
            self._begin_usb_grace()

    def _begin_usb_grace(self) -> None:
        if not self._active or self._usb_grace_active:
            return

        self._usb_grace_active = True

        # User activity must not extend the unlocked session while
        # the required second factor is unavailable.
        self._idle_timer.stop()
        self._usb_grace_timer.start()

        self.usb_key_grace_started.emit(self._usb_reconnect_grace_ms)

    def _expire_usb_grace(self) -> None:
        if not self._active or not self._usb_grace_active:
            return

        if self._keyfile_path is not None and self._expected_key_id is not None:
            current_key_id = self._probe.read_key_id(self._keyfile_path)

            if current_key_id is not None and hmac.compare_digest(
                current_key_id,
                self._expected_key_id,
            ):
                self._cancel_usb_grace(
                    restart_idle_timer=True,
                    emit_restored=True,
                )
                return

        self._usb_grace_active = False
        self._emit_usb_key_unavailable()

    def _cancel_usb_grace(
        self,
        *,
        restart_idle_timer: bool,
        emit_restored: bool,
    ) -> None:
        was_active = self._usb_grace_active

        self._usb_grace_timer.stop()
        self._usb_grace_active = False

        if was_active and restart_idle_timer and self._active and self._expected_key_id is not None:
            self._idle_timer.start(self._idle_timeout_ms)

        if was_active and emit_restored:
            self.usb_key_restored.emit()


def _require_positive_integer(
    name: str,
    value: int,
) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
