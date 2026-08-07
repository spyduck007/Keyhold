"""Integration coverage for ejecting session-used USB key volumes at exit."""

from __future__ import annotations

import subprocess

from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from usb_vault.platform.macos.usb_ejection import MacOsSessionUsbEjector
from usb_vault.ui.backend import UnlockedVault
from usb_vault.ui.main_window import MainWindow


class FakeDiskutil:
    """Record eject operations issued while a test window closes."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(
        self,
        command: tuple[str, ...],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert timeout == 3.0
        self.commands.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0)


def test_closing_window_ejects_the_usb_key_used_by_active_session(qtbot: QtBot) -> None:
    diskutil = FakeDiskutil()
    ejector = MacOsSessionUsbEjector(
        platform_name="darwin",
        command_runner=diskutil,
    )
    window = MainWindow(usb_ejector=ejector)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._activate_vault(
        UnlockedVault.create(
            vault_path="/tmp/Private.vault",
            keyfile_path="/Volumes/Hardware Key/.authkey",
            password="test password",
        ),
        (),
    )

    assert window.close()
    assert diskutil.commands == [
        ("/usr/sbin/diskutil", "eject", "/Volumes/Hardware Key"),
    ]


def test_panic_close_action_ejects_the_usb_key_and_quits(qtbot: QtBot) -> None:
    diskutil = FakeDiskutil()
    ejector = MacOsSessionUsbEjector(
        platform_name="darwin",
        command_runner=diskutil,
    )
    window = MainWindow(usb_ejector=ejector)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._activate_vault(
        UnlockedVault.create(
            vault_path="/tmp/Private.vault",
            keyfile_path="/Volumes/Hardware Key/.authkey",
            password="test password",
        ),
        (),
    )

    assert window.panic_close_action.shortcut().toString() == "Ctrl+Alt+Shift+P"
    window.panic_close_action.trigger()

    assert not window.isVisible()
    assert diskutil.commands == [
        ("/usr/sbin/diskutil", "eject", "/Volumes/Hardware Key"),
    ]
