"""End-to-end tests for backup USB keys and revocation."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import Argon2Parameters
from usb_vault.core.errors import (
    CurrentKeyRevocationError,
    KeySlotNotFoundError,
    LastKeySlotError,
    UnlockError,
)
from usb_vault.core.keys.keyfile import (
    KEY_ID_LENGTH,
)
from usb_vault.core.storage.reader import read_usb_keyfile
from usb_vault.core.vault.creator import create_vault
from usb_vault.core.vault.key_management import (
    add_usb_key,
    list_usb_keys,
    revoke_usb_key,
)
from usb_vault.core.vault.unlocker import unlock_vault

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

PASSWORD = "correct horse battery staple"


def _create_vault(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    primary_directory = tmp_path / "primary-usb"
    backup_directory = tmp_path / "backup-usb"

    primary_directory.mkdir()
    backup_directory.mkdir()

    vault_path = tmp_path / "PrivateVault.vault"
    primary_keyfile_path = primary_directory / ".authkey"
    backup_keyfile_path = backup_directory / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
        argon2_parameters=TEST_PARAMETERS,
    )

    return (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    )


def test_add_backup_key_and_unlock_with_either_key(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    ) = _create_vault(tmp_path)

    backup = add_usb_key(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
        new_keyfile_path=backup_keyfile_path,
    )

    assert backup_keyfile_path.is_file()
    assert read_usb_keyfile(backup_keyfile_path).key_id == backup.key_id

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
    ) as primary_session:
        assert primary_session.entry_count == 0

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=backup_keyfile_path,
        password=PASSWORD,
    ) as backup_session:
        assert backup_session.entry_count == 0


def test_list_keys_marks_the_key_used_to_unlock(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    ) = _create_vault(tmp_path)

    backup = add_usb_key(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
        new_keyfile_path=backup_keyfile_path,
    )
    primary_key_id = read_usb_keyfile(primary_keyfile_path).key_id

    primary_view = list_usb_keys(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
    )

    assert {key.key_id for key in primary_view} == {
        primary_key_id,
        backup.key_id,
    }
    assert {key.key_id for key in primary_view if key.is_current} == {primary_key_id}

    backup_view = list_usb_keys(
        vault_path=vault_path,
        keyfile_path=backup_keyfile_path,
        password=PASSWORD,
    )

    assert {key.key_id for key in backup_view if key.is_current} == {backup.key_id}


def test_revoke_backup_key(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    ) = _create_vault(tmp_path)

    backup = add_usb_key(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
        new_keyfile_path=backup_keyfile_path,
    )

    revoked = revoke_usb_key(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
        target_key_id=backup.key_id,
    )

    assert revoked.key_id == backup.key_id

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
    ) as session:
        assert session.entry_count == 0

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=backup_keyfile_path,
            password=PASSWORD,
        )


def test_cannot_revoke_final_key(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        _,
    ) = _create_vault(tmp_path)

    primary_key_id = read_usb_keyfile(primary_keyfile_path).key_id

    with pytest.raises(LastKeySlotError):
        revoke_usb_key(
            vault_path=vault_path,
            keyfile_path=primary_keyfile_path,
            password=PASSWORD,
            target_key_id=primary_key_id,
        )


def test_cannot_revoke_current_key(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    ) = _create_vault(tmp_path)

    add_usb_key(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
        new_keyfile_path=backup_keyfile_path,
    )
    primary_key_id = read_usb_keyfile(primary_keyfile_path).key_id

    with pytest.raises(CurrentKeyRevocationError):
        revoke_usb_key(
            vault_path=vault_path,
            keyfile_path=primary_keyfile_path,
            password=PASSWORD,
            target_key_id=primary_key_id,
        )

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=primary_keyfile_path,
        password=PASSWORD,
    ) as session:
        assert session.entry_count == 0


def test_unknown_key_cannot_be_revoked(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        _,
    ) = _create_vault(tmp_path)

    with pytest.raises(KeySlotNotFoundError):
        revoke_usb_key(
            vault_path=vault_path,
            keyfile_path=primary_keyfile_path,
            password=PASSWORD,
            target_key_id=(b"X" * KEY_ID_LENGTH),
        )


def test_existing_backup_destination_is_preserved(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    ) = _create_vault(tmp_path)

    backup_keyfile_path.write_bytes(b"existing data")
    original_vault = vault_path.read_bytes()

    with pytest.raises(FileExistsError):
        add_usb_key(
            vault_path=vault_path,
            keyfile_path=primary_keyfile_path,
            password=PASSWORD,
            new_keyfile_path=backup_keyfile_path,
        )

    assert backup_keyfile_path.read_bytes() == b"existing data"
    assert vault_path.read_bytes() == original_vault


def test_wrong_password_cannot_add_backup_key(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
        backup_keyfile_path,
    ) = _create_vault(tmp_path)

    original_vault = vault_path.read_bytes()

    with pytest.raises(UnlockError):
        add_usb_key(
            vault_path=vault_path,
            keyfile_path=primary_keyfile_path,
            password="wrong password",
            new_keyfile_path=backup_keyfile_path,
        )

    assert not backup_keyfile_path.exists()
    assert vault_path.read_bytes() == original_vault
