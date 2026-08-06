"""Tests for recovery-code presentation."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.ui.recovery_dialog import (
    RecoveryCodeDialog,
)

RECOVERY_CODE = "UVR1-AAAA-BBBB-CCCC-DDDD"


def _show_dialog(
    dialog: RecoveryCodeDialog,
) -> None:
    dialog.show()
    QApplication.processEvents()


def test_dialog_displays_recovery_code(
    qtbot: QtBot,
) -> None:
    dialog = RecoveryCodeDialog(RECOVERY_CODE)
    qtbot.addWidget(dialog)
    _show_dialog(dialog)

    assert dialog.code_edit.toPlainText() == RECOVERY_CODE
    assert not dialog.done_button.isEnabled()


def test_acknowledgement_enables_continue(
    qtbot: QtBot,
) -> None:
    dialog = RecoveryCodeDialog(RECOVERY_CODE)
    qtbot.addWidget(dialog)
    _show_dialog(dialog)

    dialog.acknowledgement_checkbox.setChecked(True)
    QApplication.processEvents()

    assert dialog.acknowledgement_checkbox.isChecked()
    assert dialog.done_button.isEnabled()


def test_copy_button_places_code_on_clipboard(
    qtbot: QtBot,
) -> None:
    dialog = RecoveryCodeDialog(RECOVERY_CODE)
    qtbot.addWidget(dialog)
    _show_dialog(dialog)

    clipboard = QApplication.clipboard()
    clipboard.clear()

    QTest.mouseClick(
        dialog.copy_button,
        Qt.MouseButton.LeftButton,
    )
    QApplication.processEvents()

    assert clipboard.text() == RECOVERY_CODE
