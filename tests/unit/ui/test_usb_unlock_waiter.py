"""Tests for background registered-USB polling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pytestqt.qtbot import (
    QtBot,
)

from usb_vault.ui.usb_unlock_waiter import (
    UsbUnlockWaiter,
)

VAULT_PATH = Path("/tmp/Private.vault")
KEYFILE_PATH = Path("/Volumes/USB/.authkey")


@dataclass
class SequenceKeyLocator:
    """Return configured results across successive scans."""

    results: list[Path | None] = field(default_factory=list)
    calls: int = 0

    def find_matching_keyfile(
        self,
        vault_path: Path,
    ) -> Path | None:
        assert vault_path == VAULT_PATH

        self.calls += 1

        if not self.results:
            return None

        return self.results.pop(0)


class FailingKeyLocator:
    """Simulate a vault or filesystem scan failure."""

    def find_matching_keyfile(
        self,
        vault_path: Path,
    ) -> Path | None:
        assert vault_path == VAULT_PATH

        raise OSError("simulated USB scan failure")


def test_waiter_polls_until_key_appears(
    qtbot: QtBot,
) -> None:
    locator = SequenceKeyLocator(
        results=[
            None,
            KEYFILE_PATH,
        ]
    )
    waiter = UsbUnlockWaiter(
        locator=locator,
        poll_interval_ms=20,
    )

    with qtbot.waitSignal(
        waiter.keyfile_found,
        timeout=2_000,
    ) as signal:
        waiter.start(VAULT_PATH)

    assert signal.args == [
        KEYFILE_PATH,
    ]
    assert locator.calls == 2
    assert not waiter.is_active
    assert waiter.vault_path is None


def test_cancel_ignores_future_scan_results(
    qtbot: QtBot,
) -> None:
    locator = SequenceKeyLocator(
        results=[
            None,
            KEYFILE_PATH,
        ]
    )
    waiter = UsbUnlockWaiter(
        locator=locator,
        poll_interval_ms=100,
    )
    found_paths: list[Path] = []

    waiter.keyfile_found.connect(found_paths.append)

    waiter.start(VAULT_PATH)

    qtbot.waitUntil(
        lambda: locator.calls >= 1,
        timeout=1_000,
    )

    waiter.cancel()
    qtbot.wait(200)

    assert found_paths == []
    assert not waiter.is_active


def test_scan_failure_stops_waiting(
    qtbot: QtBot,
) -> None:
    waiter = UsbUnlockWaiter(
        locator=FailingKeyLocator(),
        poll_interval_ms=20,
    )

    with qtbot.waitSignal(
        waiter.scan_failed,
        timeout=1_000,
    ) as signal:
        waiter.start(VAULT_PATH)

    assert signal.args == [
        "simulated USB scan failure",
    ]
    assert not waiter.is_active
