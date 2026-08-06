"""Tests for the desktop unlock page."""

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtTest import (
    QTest,
)
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
)
from pytestqt.qtbot import (
    QtBot,
)

from usb_vault.ui.pages.unlock_page import (
    UnlockPage,
)


def _show_page(
    page: UnlockPage,
) -> None:
    page.show()
    QApplication.processEvents()


def test_unlock_page_emits_complete_credentials(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.keyfile_path_edit.setText("/Volumes/USB/.authkey")
    page.password_edit.setText("test password")

    with qtbot.waitSignal(
        page.unlock_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.unlock_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        "/tmp/Private.vault",
        "/Volumes/USB/.authkey",
        "test password",
    ]


def test_unlock_page_allows_automatic_key_detection(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")
    page.password_edit.setText("test password")

    with qtbot.waitSignal(
        page.unlock_requested,
        timeout=1_000,
    ) as signal:
        QTest.mouseClick(
            page.unlock_button,
            Qt.MouseButton.LeftButton,
        )

    assert signal.args == [
        "/tmp/Private.vault",
        "",
        "test password",
    ]


def test_unlock_page_requires_vault_path(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.password_edit.setText("test password")

    QTest.mouseClick(
        page.unlock_button,
        Qt.MouseButton.LeftButton,
    )

    assert page.error_label.isVisible()
    assert page.error_label.text() == "Choose a vault file."


def test_unlock_page_requires_password(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.vault_path_edit.setText("/tmp/Private.vault")

    QTest.mouseClick(
        page.unlock_button,
        Qt.MouseButton.LeftButton,
    )

    assert page.error_label.isVisible()
    assert page.error_label.text() == "Enter the vault password."


def test_show_password_checkbox_changes_echo_mode(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    assert page.password_edit.echoMode() == QLineEdit.EchoMode.Password

    QTest.mouseClick(
        page.show_password_checkbox,
        Qt.MouseButton.LeftButton,
    )

    assert page.password_edit.echoMode() == QLineEdit.EchoMode.Normal


def test_reset_after_lock_clears_password_and_error(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.password_edit.setText("secret")
    page.show_error("Something failed.")

    page.reset_after_lock()

    assert page.password_edit.text() == ""
    assert not (page.error_label.isVisible())
