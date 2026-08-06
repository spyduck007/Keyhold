"""Tests for the single-operation Qt background runner."""

from __future__ import annotations

import threading

import pytest
from pytestqt.qtbot import QtBot

from usb_vault.ui.task_runner import (
    TaskRunner,
)


def test_task_runs_outside_gui_thread(
    qtbot: QtBot,
) -> None:
    runner = TaskRunner()
    gui_thread_id = threading.get_ident()
    results: list[int] = []
    failures: list[str] = []

    runner.start(
        threading.get_ident,
        succeeded=lambda value: results.append(int(value)),
        failed=failures.append,
    )

    qtbot.waitUntil(
        lambda: not runner.is_busy,
        timeout=2_000,
    )

    assert failures == []
    assert len(results) == 1
    assert results[0] != gui_thread_id


def test_task_failure_returns_message(
    qtbot: QtBot,
) -> None:
    runner = TaskRunner()
    failures: list[str] = []

    def fail() -> object:
        raise ValueError("simulated failure")

    runner.start(
        fail,
        succeeded=lambda value: None,
        failed=failures.append,
    )

    qtbot.waitUntil(
        lambda: not runner.is_busy,
        timeout=2_000,
    )

    assert failures == [
        "simulated failure",
    ]


def test_runner_rejects_overlapping_tasks(
    qtbot: QtBot,
) -> None:
    runner = TaskRunner()
    started = threading.Event()
    release = threading.Event()

    def blocking_operation() -> object:
        started.set()

        if not release.wait(timeout=2):
            raise RuntimeError("test release timed out")

        return "finished"

    runner.start(
        blocking_operation,
        succeeded=lambda value: None,
        failed=lambda message: None,
    )

    qtbot.waitUntil(
        started.is_set,
        timeout=2_000,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match=("already in progress"),
        ):
            runner.start(
                lambda: None,
                succeeded=lambda value: None,
                failed=lambda message: None,
            )
    finally:
        release.set()

    qtbot.waitUntil(
        lambda: not runner.is_busy,
        timeout=2_000,
    )
