"""Tests for USB-waiting states on the unlock page."""

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtTest import (
    QTest,
)
from PySide6.QtWidgets import (
    QApplication,
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


def test_waiting_state_disables_credentials_and_allows_cancel(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.begin_waiting_for_usb()

    assert page.is_waiting_for_usb
    assert not page.is_unlocking
    assert not page.password_edit.isEnabled()
    assert not page.unlock_button.isEnabled()
    assert page.cancel_button.isEnabled()
    assert page.waiting_label.isVisible()

    with qtbot.waitSignal(
        page.cancel_requested,
        timeout=1_000,
    ):
        QTest.mouseClick(
            page.cancel_button,
            Qt.MouseButton.LeftButton,
        )


def test_unlocking_state_disables_cancel(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.begin_unlocking()

    assert not page.is_waiting_for_usb
    assert page.is_unlocking
    assert not page.unlock_button.isEnabled()
    assert not page.cancel_button.isEnabled()


def test_end_waiting_restores_form(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.begin_waiting_for_usb()
    page.end_waiting()

    assert not page.is_waiting_for_usb
    assert not page.is_unlocking
    assert page.password_edit.isEnabled()
    assert page.unlock_button.isEnabled()
    assert page.cancel_button.isEnabled()
    assert not page.waiting_label.isVisible()
    assert page.unlock_button.text() == "Continue"


def test_reset_after_lock_clears_waiting_state(
    qtbot: QtBot,
) -> None:
    page = UnlockPage()
    qtbot.addWidget(page)
    _show_page(page)

    page.password_edit.setText("secret")
    page.begin_waiting_for_usb()
    page.reset_after_lock()

    assert not page.is_waiting_for_usb
    assert not page.is_unlocking
    assert page.password_edit.text() == ""
