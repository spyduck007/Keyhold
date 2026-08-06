"""Tests for USB-key reconnection grace-period monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pytestqt.qtbot import (
    QtBot,
)

from usb_vault.ui.usb_grace import (
    UsbGraceSessionGuard,
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


def test_removed_key_starts_grace_then_locks(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=50,
    )
    guard.start(KEYFILE_PATH)

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_grace_started,
        timeout=1_000,
    ) as grace_signal:
        guard.check_keyfile_now()

    assert grace_signal.args == [
        50,
    ]
    assert guard.is_active
    assert guard.is_in_usb_grace

    with qtbot.waitSignal(
        guard.usb_key_unavailable,
        timeout=1_000,
    ):
        pass

    assert not guard.is_active
    assert not guard.is_in_usb_grace


def test_same_key_cancels_grace(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=500,
    )
    guard.start(KEYFILE_PATH)

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_grace_started,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    probe.key_id = KEY_ID_A

    with qtbot.waitSignal(
        guard.usb_key_restored,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    assert guard.is_active
    assert not guard.is_in_usb_grace

    guard.stop()


def test_different_key_does_not_cancel_grace(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=50,
    )
    guard.start(KEYFILE_PATH)

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_grace_started,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    probe.key_id = KEY_ID_B
    guard.check_keyfile_now()

    with qtbot.waitSignal(
        guard.usb_key_unavailable,
        timeout=1_000,
    ):
        pass

    assert not guard.is_active


def test_stop_cancels_pending_grace(
    qtbot: QtBot,
) -> None:
    probe = FakeKeyfileProbe(key_id=KEY_ID_A)
    guard = UsbGraceSessionGuard(
        probe=probe,
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=50,
    )
    unavailable_count: list[bool] = []

    guard.usb_key_unavailable.connect(lambda: unavailable_count.append(True))
    guard.start(KEYFILE_PATH)

    probe.key_id = None

    with qtbot.waitSignal(
        guard.usb_key_grace_started,
        timeout=1_000,
    ):
        guard.check_keyfile_now()

    guard.stop()
    qtbot.wait(100)

    assert unavailable_count == []
    assert not guard.is_active
    assert not guard.is_in_usb_grace


def test_initially_invalid_key_still_fails_immediately(
    qtbot: QtBot,
) -> None:
    guard = UsbGraceSessionGuard(
        probe=FakeKeyfileProbe(key_id=None),
        usb_poll_interval_ms=10_000,
        idle_timeout_ms=10_000,
        usb_reconnect_grace_ms=500,
    )

    with qtbot.waitSignal(
        guard.usb_key_unavailable,
        timeout=1_000,
    ):
        guard.start(KEYFILE_PATH)

    assert not guard.is_active
    assert not guard.is_in_usb_grace
