"""Tests for mutable desktop workflow secrets."""

import pytest

from usb_vault.ui.workflow_secrets import (
    MutableTextSecret,
)


def test_secret_returns_original_unicode_text() -> None:
    secret = MutableTextSecret.from_text("correct café password")

    assert secret.text() == "correct café password"


def test_secret_can_be_overwritten() -> None:
    secret = MutableTextSecret.from_text("test password")

    secret.close()

    assert secret.is_closed

    with pytest.raises(
        RuntimeError,
        match="secret is closed",
    ):
        secret.text()


def test_empty_secret_requires_explicit_permission() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        MutableTextSecret.from_text("")

    secret = MutableTextSecret.from_text(
        "",
        allow_empty=True,
    )

    assert secret.text() == ""
