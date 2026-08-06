"""Tests for the desktop vault-setup page."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
)
from pytestqt.qtbot import QtBot

from usb_vault.ui.pages.setup_page import (
    SetupPage,
)


class FakeUsbVolumeLocator:
    """Return deterministic USB volumes without requiring macOS mounts."""

    def __init__(
        self,
        volume_paths: tuple[Path, ...],
    ) -> None:
        self.volume_paths = volume_paths

    def external_usb_volumes(self) -> tuple[Path, ...]:
        return self.volume_paths


def _show_page(
    page: SetupPage,
) -> None:
    page.show()
    QApplication.processEvents()


def test_setup_page_emits_complete_request(
    qtbot: QtBot,
) -> None:
    usb_path = Path("/Volumes/Hardware Key")
    page = SetupPage(
        usb_volume_locator=FakeUsbVolumeLocator((usb_path,)),
    )
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.usb_volume_combo.setCurrentIndex(1)
    page.password_edit.setText("test password")
    page.confirmation_edit.setText("test password")

    with qtbot.waitSignal(
        page.setup_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.create_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        "/tmp/Private.vault",
        "/Volumes/Hardware Key/.authkey",
        "test password",
    ]


def test_setup_page_selects_usb_and_generates_hidden_keyfile_path(
    qtbot: QtBot,
) -> None:
    page = SetupPage(
        usb_volume_locator=FakeUsbVolumeLocator(
            (
                Path("/Volumes/Alpha"),
                Path("/Volumes/Bravo"),
            )
        ),
    )
    qtbot.addWidget(page)
    _show_page(page)

    assert page.usb_volume_combo.itemText(1) == "Alpha"
    assert page.usb_volume_combo.itemText(2) == "Bravo"
    assert page.keyfile_path_edit.isReadOnly()

    page.usb_volume_combo.setCurrentIndex(2)

    assert page.keyfile_path_edit.text() == "/Volumes/Bravo/.authkey"


def test_setup_page_rejects_mismatched_passwords(
    qtbot: QtBot,
) -> None:
    page = SetupPage(
        usb_volume_locator=FakeUsbVolumeLocator((Path("/Volumes/USB"),)),
    )
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.usb_volume_combo.setCurrentIndex(1)
    page.password_edit.setText("first password")
    page.confirmation_edit.setText("second password")

    QTest.mouseClick(
        page.create_button,
        Qt.MouseButton.LeftButton,
    )

    assert page.error_label.isVisible()
    assert page.error_label.text() == "Passwords do not match."


def test_show_passwords_changes_both_echo_modes(
    qtbot: QtBot,
) -> None:
    page = SetupPage()
    qtbot.addWidget(page)
    _show_page(page)

    QTest.mouseClick(
        page.show_password_checkbox,
        Qt.MouseButton.LeftButton,
    )

    assert page.password_edit.echoMode() == QLineEdit.EchoMode.Normal
    assert page.confirmation_edit.echoMode() == QLineEdit.EchoMode.Normal


def test_cancel_resets_setup_form(
    qtbot: QtBot,
) -> None:
    page = SetupPage(
        usb_volume_locator=FakeUsbVolumeLocator((Path("/Volumes/USB"),)),
    )
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.usb_volume_combo.setCurrentIndex(1)
    page.password_edit.setText("test password")

    with qtbot.waitSignal(
        page.cancel_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.cancel_button,
            Qt.MouseButton.LeftButton,
        )

    assert page.vault_path_edit.text() == ""
    assert page.keyfile_path_edit.text() == ""
    assert page.password_edit.text() == ""
