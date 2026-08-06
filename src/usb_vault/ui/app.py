"""Desktop application entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import (
    QApplication,
)

from usb_vault.ui.main_window import (
    MainWindow,
)


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Launch the USB Vault desktop application."""
    if QApplication.instance() is not None:
        raise RuntimeError("a QApplication already exists")

    arguments = list(argv) if argv is not None else sys.argv

    application = QApplication(arguments)
    application.setApplicationName("USB Vault")
    application.setOrganizationName("USB Vault")

    window = MainWindow()
    window.show()

    return application.exec()
