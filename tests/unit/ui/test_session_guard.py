"""Tests for USB identity and idle-timeout monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QObject,
)
from pytestqt.qtbot import QtBot

from usb_vault.ui.session_guard import (
    SessionGuard,
    UserActivityFilter,
)

KEYFILE_PATH = Path("/Volumes/TestUSB/.authkey")
KEY_ID_A = b"A" * 16
KEY_ID_B = b"B" * 16


@dataclass
class FakeKeyfileProbe:
    """Controllable keyfile identity probe."""

    key_id: bytes | None

    def read_key_id(
        self,
        keyfile_path: Path,
    ) -> bytes | None:
        assert keyfile_path == KEYFILE_PATH
        return self.key_id


def test_guard_starts_with_expected_identity() -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = SessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )

    guard.start(KEYFILE_PATH)

    assert guard.is_active
    assert guard.keyfile_path == KEYFILE_PATH

    guard.stop()

    assert not guard.is_active
    assert guard.keyfile_path is None


def test_missing_keyfile_emits_lock_signal(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=None)
    guard = SessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )

    with qtbot.waitSignal(
        guard.usb_key_unavailable,
        timeout=1_000,
    ):
        guard.start(KEYFILE_PATH)

    assert not guard.is_active


def test_removed_keyfile_emits_lock_signal(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = SessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    guard.start(KEYFILE_PATH)

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_unavailable,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    assert not guard.is_active


def test_replaced_keyfile_emits_lock_signal(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = SessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
    )
    guard.start(KEYFILE_PATH)

    probe.key_id = KEY_ID_B

    with qtbot.waitSignal(
        guard.usb_key_unavailable,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    assert not guard.is_active


def test_idle_timer_emits_timeout(
    qtbot: QtBot,
) -> None:
    guard = SessionGuard(
        probe=FakeKeyfileProbe(key_id=KEY_ID_A),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=20,
    )

    with qtbot.waitSignal(
        guard.idle_timeout,
        timeout=1_000,
    ):
        guard.start(KEYFILE_PATH)

    assert not guard.is_active


def test_activity_filter_emits_for_key_press(
    qtbot: QtBot,
) -> None:
    activity_filter = UserActivityFilter()
    watched = QObject()
    event = QEvent(QEvent.Type.KeyPress)

    with qtbot.waitSignal(
        activity_filter.activity,
        timeout=1_000,
    ):
        consumed = activity_filter.eventFilter(
            watched,
            event,
        )

    assert not consumed
