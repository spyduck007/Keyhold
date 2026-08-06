"""Desktop application entry point."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import (
    QApplication,
)

from usb_vault.ui.fully_async_window import (
    FullyAsyncSecurityMainWindow,
)
from usb_vault.ui.session_guard import (
    DEFAULT_IDLE_TIMEOUT_MS,
    DEFAULT_USB_POLL_INTERVAL_MS,
    SessionGuard,
)

USB_POLL_ENVIRONMENT_VARIABLE = "USB_VAULT_USB_POLL_SECONDS"
IDLE_TIMEOUT_ENVIRONMENT_VARIABLE = "USB_VAULT_IDLE_TIMEOUT_SECONDS"


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Launch the fully responsive monitored desktop application."""
    if QApplication.instance() is not None:
        raise RuntimeError("a QApplication already exists")

    arguments = list(argv) if argv is not None else sys.argv

    application = QApplication(arguments)
    application.setApplicationName("USB Vault")
    application.setOrganizationName("USB Vault")

    session_guard = SessionGuard(
        usb_poll_interval_ms=(
            _environment_duration_ms(
                USB_POLL_ENVIRONMENT_VARIABLE,
                DEFAULT_USB_POLL_INTERVAL_MS,
            )
        ),
        idle_timeout_ms=(
            _environment_duration_ms(
                IDLE_TIMEOUT_ENVIRONMENT_VARIABLE,
                DEFAULT_IDLE_TIMEOUT_MS,
            )
        ),
    )

    window = FullyAsyncSecurityMainWindow(session_guard=session_guard)
    window.show()

    return application.exec()


def _environment_duration_ms(
    variable_name: str,
    default_milliseconds: int,
) -> int:
    """Read a positive whole-second duration from the environment."""
    raw_value = os.environ.get(variable_name)

    if raw_value is None:
        return default_milliseconds

    try:
        seconds = int(raw_value)
    except ValueError:
        raise RuntimeError(f"{variable_name} must be a positive whole number.") from None

    if seconds <= 0:
        raise RuntimeError(f"{variable_name} must be a positive whole number.")

    return seconds * 1_000
