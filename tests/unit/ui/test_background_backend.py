"""Tests for background credential lifetime."""

from pathlib import Path

import pytest

from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.background_backend import (
    BackgroundVaultCredentials,
)


def test_background_credentials_survive_ui_lock_and_can_be_cleared(
    tmp_path: Path,
) -> None:
    vault = UnlockedVault.create(
        vault_path=(tmp_path / "Private.vault"),
        keyfile_path=(tmp_path / ".authkey"),
        password="test password",
    )
    credentials = BackgroundVaultCredentials.from_unlocked(vault)

    vault.close()

    assert credentials.password_bytes() == b"test password"

    credentials.close()

    assert credentials.is_closed

    with pytest.raises(
        RuntimeError,
        match="credentials are closed",
    ):
        credentials.password_bytes()
