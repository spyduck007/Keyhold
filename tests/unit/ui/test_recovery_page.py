"""Tests for the desktop recovery page."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.ui.pages.recovery_page import (
    RecoveryPage,
)

RECOVERY_CODE = "UVR1-AAAA-BBBB-CCCC-DDDD"


class FakeUsbVolumeLocator:
    """Return deterministic mounted USB roots."""

    def external_usb_volumes(self) -> tuple[Path, ...]:
        return (Path("/Volumes/Recovery Key"),)


def _show_page(
    page: RecoveryPage,
) -> None:
    page.show()
    QApplication.processEvents()


def test_recovery_page_emits_complete_request(
    qtbot: QtBot,
) -> None:
    page = RecoveryPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.new_keyfile_path_edit.setText("/Volumes/NewUSB/.authkey")
    page.password_edit.setText("test password")
    page.confirmation_edit.setText("test password")
    page.recovery_code_edit.setPlainText(RECOVERY_CODE)

    with qtbot.waitSignal(
        page.recovery_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.recover_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        "/tmp/Private.vault",
        "/Volumes/NewUSB/.authkey",
        "test password",
        RECOVERY_CODE,
        True,
    ]


def test_previous_keys_are_revoked_by_default(
    qtbot: QtBot,
) -> None:
    page = RecoveryPage()
    qtbot.addWidget(page)
    _show_page(page)

    assert page.replace_existing_keys_checkbox.isChecked()


def test_recovery_selects_usb_without_a_keyfile_dialog(
    qtbot: QtBot,
) -> None:
    page = RecoveryPage(usb_volume_locator=FakeUsbVolumeLocator())
    qtbot.addWidget(page)
    _show_page(page)

    page.usb_volume_combo.setCurrentIndex(1)

    assert page.new_keyfile_path_edit.isReadOnly()
    assert page.new_keyfile_path_edit.text() == "/Volumes/Recovery Key/.authkey"


def test_recovery_page_rejects_mismatched_passwords(
    qtbot: QtBot,
) -> None:
    page = RecoveryPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.new_keyfile_path_edit.setText("/Volumes/NewUSB/.authkey")
    page.password_edit.setText("first password")
    page.confirmation_edit.setText("second password")
    page.recovery_code_edit.setPlainText(RECOVERY_CODE)

    QTest.mouseClick(
        page.recover_button,
        Qt.MouseButton.LeftButton,
    )

    assert page.error_label.isVisible()
    assert page.error_label.text() == "Passwords do not match."


def test_clear_sensitive_fields_removes_credentials(
    qtbot: QtBot,
) -> None:
    page = RecoveryPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.password_edit.setText("test password")
    page.confirmation_edit.setText("test password")
    page.recovery_code_edit.setPlainText(RECOVERY_CODE)

    page.clear_sensitive_fields()

    assert page.password_edit.text() == ""
    assert page.confirmation_edit.text() == ""
    assert page.recovery_code_edit.toPlainText() == ""
