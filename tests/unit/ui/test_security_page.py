"""Tests for the desktop Security Center page."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from pytestqt.qtbot import QtBot

from usb_vault.core.vault.key_management import (
    UsbKeySummary,
)
from usb_vault.ui.pages.security_page import (
    SecurityPage,
)
from usb_vault.ui.security_backend import (
    SecuritySnapshot,
)

CURRENT_KEY_ID = b"A" * 16
BACKUP_KEY_ID = b"B" * 16
RECOVERY_CODE = "UVR1-AAAA-BBBB-CCCC-DDDD"


def _show_page(
    page: SecurityPage,
) -> None:
    page.show()
    QApplication.processEvents()


def _table_text(
    page: SecurityPage,
    row: int,
    column: int,
) -> str:
    item = page.keys_table.item(
        row,
        column,
    )
    assert item is not None
    return item.text()


def test_snapshot_displays_current_and_backup_keys(
    qtbot: QtBot,
) -> None:
    page = SecurityPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_snapshot(
        SecuritySnapshot(
            keys=(
                UsbKeySummary(
                    key_id=CURRENT_KEY_ID,
                    is_current=True,
                ),
                UsbKeySummary(
                    key_id=BACKUP_KEY_ID,
                ),
            ),
            recovery_configured=True,
        )
    )

    assert page.keys_table.rowCount() == 2
    assert (
        _table_text(
            page,
            0,
            1,
        )
        == "Current"
    )
    assert (
        _table_text(
            page,
            1,
            1,
        )
        == "Backup"
    )
    assert page.recovery_code_edit.isVisible()


def test_current_key_cannot_be_selected_for_revocation(
    qtbot: QtBot,
) -> None:
    page = SecurityPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_snapshot(
        SecuritySnapshot(
            keys=(
                UsbKeySummary(
                    key_id=CURRENT_KEY_ID,
                    is_current=True,
                ),
                UsbKeySummary(
                    key_id=BACKUP_KEY_ID,
                ),
            ),
            recovery_configured=False,
        )
    )

    page.keys_table.selectRow(0)

    assert not page.revoke_key_button.isEnabled()

    page.keys_table.selectRow(1)

    assert page.revoke_key_button.isEnabled()


def test_password_change_emits_complete_request(
    qtbot: QtBot,
) -> None:
    page = SecurityPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_snapshot(
        SecuritySnapshot(
            keys=(
                UsbKeySummary(
                    key_id=CURRENT_KEY_ID,
                    is_current=True,
                ),
                UsbKeySummary(
                    key_id=BACKUP_KEY_ID,
                ),
            ),
            recovery_configured=True,
        )
    )

    page.current_password_edit.setText("old password")
    page.new_password_edit.setText("new password")
    page.confirmation_edit.setText("new password")
    page.add_password_keyfile_path("/Volumes/Backup/.authkey")
    page.recovery_code_edit.setPlainText(RECOVERY_CODE)

    with qtbot.waitSignal(
        page.password_change_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.change_password_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        "old password",
        "new password",
        ("/Volumes/Backup/.authkey",),
        RECOVERY_CODE,
    ]


def test_password_change_requires_exact_keyfile_count(
    qtbot: QtBot,
) -> None:
    page = SecurityPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.set_snapshot(
        SecuritySnapshot(
            keys=(
                UsbKeySummary(
                    key_id=CURRENT_KEY_ID,
                    is_current=True,
                ),
                UsbKeySummary(
                    key_id=BACKUP_KEY_ID,
                ),
            ),
            recovery_configured=False,
        )
    )

    page.current_password_edit.setText("old password")
    page.new_password_edit.setText("new password")
    page.confirmation_edit.setText("new password")

    QTest.mouseClick(
        page.change_password_button,
        Qt.MouseButton.LeftButton,
    )

    assert "Select exactly 1" in page.error_label.text()
