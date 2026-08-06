"""Tests for mutable desktop session credentials."""

from pathlib import Path

import pytest

from usb_vault.ui.backend import (
    UnlockedVault,
)


def test_unlocked_vault_exposes_credentials_while_open() -> None:
    vault = UnlockedVault.create(
        vault_path=Path("Private.vault"),
        keyfile_path=Path(".authkey"),
        password="test password",
    )

    assert vault.password_bytes() == b"test password"
    assert not vault.is_closed


def test_close_makes_credentials_unavailable() -> None:
    vault = UnlockedVault.create(
        vault_path=Path("Private.vault"),
        keyfile_path=Path(".authkey"),
        password="test password",
    )

    vault.close()

    assert vault.is_closed

    with pytest.raises(
        RuntimeError,
        match="session is locked",
    ):
        vault.password_bytes()


def test_close_is_idempotent() -> None:
    vault = UnlockedVault.create(
        vault_path="Private.vault",
        keyfile_path=".authkey",
        password="test password",
    )

    vault.close()
    vault.close()

    assert vault.is_closed


def test_empty_password_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        UnlockedVault.create(
            vault_path="Private.vault",
            keyfile_path=".authkey",
            password="",
        )
