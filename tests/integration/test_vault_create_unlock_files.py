"""End-to-end tests for creating and unlocking on-disk vault files."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import Argon2Parameters
from usb_vault.core.errors import UnlockError
from usb_vault.core.keys.keyfile import create_usb_keyfile
from usb_vault.core.storage.reader import (
    read_usb_keyfile,
    read_vault_container,
)
from usb_vault.core.storage.writer import write_usb_keyfile
from usb_vault.core.vault.creator import create_vault
from usb_vault.core.vault.unlocker import unlock_vault

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def test_create_and_unlock_empty_vault(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "PrivateVault.vault"
    keyfile_path = tmp_path / ".authkey"

    result = create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=("correct horse battery staple"),
        argon2_parameters=TEST_PARAMETERS,
    )

    assert vault_path.is_file()
    assert keyfile_path.is_file()
    assert read_usb_keyfile(keyfile_path).key_id == result.key_id
    assert read_vault_container(vault_path).header.vault_id == result.vault_id

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=("correct horse battery staple"),
    ) as session:
        assert session.entry_count == 0
        assert session.header.vault_id == result.vault_id


def test_wrong_password_cannot_unlock_created_vault(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "PrivateVault.vault"
    keyfile_path = tmp_path / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password="correct password",
        argon2_parameters=TEST_PARAMETERS,
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password="wrong password",
        )


def test_wrong_keyfile_cannot_unlock_created_vault(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "PrivateVault.vault"
    keyfile_path = tmp_path / ".authkey"
    wrong_keyfile_path = tmp_path / ".wrong-authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password="correct password",
        argon2_parameters=TEST_PARAMETERS,
    )
    write_usb_keyfile(
        wrong_keyfile_path,
        create_usb_keyfile(),
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=wrong_keyfile_path,
            password="correct password",
        )


def test_modified_encrypted_manifest_is_rejected(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "PrivateVault.vault"
    keyfile_path = tmp_path / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password="correct password",
        argon2_parameters=TEST_PARAMETERS,
    )

    data = bytearray(vault_path.read_bytes())
    data[-1] ^= 0x01
    vault_path.write_bytes(data)

    with pytest.raises(UnlockError):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password="correct password",
        )


def test_create_refuses_existing_destinations(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "PrivateVault.vault"
    keyfile_path = tmp_path / ".authkey"
    vault_path.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        create_vault(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password="correct password",
            argon2_parameters=TEST_PARAMETERS,
        )

    assert vault_path.read_bytes() == b"existing"
    assert not keyfile_path.exists()
