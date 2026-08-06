"""Tests for smooth page transitions."""

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from usb_vault.ui.animated_stack import AnimatedStackedWidget


def test_transition_selects_target_immediately_and_settles(qtbot: QtBot) -> None:
    stack = AnimatedStackedWidget()
    first_page = QWidget()
    second_page = QWidget()
    stack.addWidget(first_page)
    stack.addWidget(second_page)
    stack.resize(640, 480)
    qtbot.addWidget(stack)
    stack.show()
    QApplication.processEvents()

    stack.setCurrentWidget(second_page)

    assert stack.currentWidget() is second_page

    qtbot.wait(380)

    assert second_page.pos() == QPoint(0, 0)
    assert second_page.isVisible()
    assert not first_page.isVisible()


def test_new_transition_safely_replaces_active_transition(qtbot: QtBot) -> None:
    stack = AnimatedStackedWidget()
    pages = tuple(QWidget() for _ in range(3))
    for page in pages:
        stack.addWidget(page)

    stack.resize(640, 480)
    qtbot.addWidget(stack)
    stack.show()
    QApplication.processEvents()

    stack.setCurrentWidget(pages[1])
    stack.setCurrentWidget(pages[2])
    qtbot.wait(380)

    assert stack.currentWidget() is pages[2]
    assert pages[2].pos() == QPoint(0, 0)
    assert pages[2].isVisible()
