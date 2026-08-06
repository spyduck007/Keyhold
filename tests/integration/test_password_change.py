"""End-to-end tests for secure vault password rotation."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import Argon2Parameters
from usb_vault.core.errors import (
    KeyfileSetError,
    UnlockError,
)
from usb_vault.core.keys.keyfile import create_usb_keyfile
from usb_vault.core.storage.reader import read_vault_container
from usb_vault.core.storage.writer import write_usb_keyfile
from usb_vault.core.vault.creator import create_vault
from usb_vault.core.vault.key_management import add_usb_key
from usb_vault.core.vault.operations import (
    add_file,
    extract_file,
)
from usb_vault.core.vault.password_management import (
    change_vault_password,
)
from usb_vault.core.vault.unlocker import unlock_vault

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

OLD_PASSWORD = "old correct password"
NEW_PASSWORD = "new correct password"


def _create_vault(
    tmp_path: Path,
) -> tuple[Path, Path]:
    primary_directory = tmp_path / "primary-usb"
    primary_directory.mkdir()

    vault_path = tmp_path / "PrivateVault.vault"
    primary_keyfile_path = primary_directory / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=OLD_PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )

    return (
        vault_path,
        primary_keyfile_path,
    )


def test_change_password_preserves_encrypted_files(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    source_path = tmp_path / "notes.txt"
    output_path = tmp_path / "extracted-notes.txt"
    source_contents = b"important encrypted notes\n"
    source_path.write_bytes(source_contents)

    add_file(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=OLD_PASSWORD,
        source_path=source_path,
    )

    before = read_vault_container(vault_path)

    result = change_vault_password(
        vault_path=vault_path,
        current_keyfile_path=(primary_keyfile_path),
        current_password=(OLD_PASSWORD),
        new_password=NEW_PASSWORD,
    )

    after = read_vault_container(vault_path)

    assert result.vault_id == before.header.vault_id
    assert result.key_count == 1
    assert after.header.vault_id == before.header.vault_id
    assert after.header.argon2_salt != before.header.argon2_salt
    assert after.encrypted_manifest == before.encrypted_manifest
    assert after.blobs == before.blobs
    assert (
        after.header.key_slots[0].wrapped_master_key
        != before.header.key_slots[0].wrapped_master_key
    )

    with pytest.raises(
        UnlockError,
        match=(r"^Unable to unlock vault\.$"),
    ):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=(primary_keyfile_path),
            password=OLD_PASSWORD,
        )

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=NEW_PASSWORD,
    ) as session:
        assert session.entry_count == 1

    extract_file(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=NEW_PASSWORD,
        stored_name="notes.txt",
        destination_path=output_path,
    )

    assert output_path.read_bytes() == source_contents


def test_change_password_updates_every_usb_key(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    backup_directory = tmp_path / "backup-usb"
    backup_directory.mkdir()
    backup_keyfile_path = backup_directory / ".authkey"

    add_usb_key(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=OLD_PASSWORD,
        new_keyfile_path=(backup_keyfile_path),
    )

    result = change_vault_password(
        vault_path=vault_path,
        current_keyfile_path=(primary_keyfile_path),
        current_password=(OLD_PASSWORD),
        new_password=NEW_PASSWORD,
        additional_keyfile_paths=(backup_keyfile_path,),
    )

    assert result.key_count == 2

    for keyfile_path in (
        primary_keyfile_path,
        backup_keyfile_path,
    ):
        with pytest.raises(UnlockError):
            unlock_vault(
                vault_path=vault_path,
                keyfile_path=(keyfile_path),
                password=OLD_PASSWORD,
            )

        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=(keyfile_path),
            password=NEW_PASSWORD,
        ) as session:
            assert session.entry_count == 0


def test_all_registered_keyfiles_are_required(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    backup_directory = tmp_path / "backup-usb"
    backup_directory.mkdir()
    backup_keyfile_path = backup_directory / ".authkey"

    add_usb_key(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=OLD_PASSWORD,
        new_keyfile_path=(backup_keyfile_path),
    )

    original_vault = vault_path.read_bytes()

    with pytest.raises(
        KeyfileSetError,
        match=("exactly one keyfile"),
    ):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(primary_keyfile_path),
            current_password=(OLD_PASSWORD),
            new_password=(NEW_PASSWORD),
        )

    assert vault_path.read_bytes() == original_vault

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=OLD_PASSWORD,
    ) as session:
        assert session.entry_count == 0


def test_unknown_keyfile_is_rejected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    unknown_keyfile_path = tmp_path / "unknown.authkey"
    write_usb_keyfile(
        unknown_keyfile_path,
        create_usb_keyfile(),
    )

    original_vault = vault_path.read_bytes()

    with pytest.raises(KeyfileSetError):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(primary_keyfile_path),
            current_password=(OLD_PASSWORD),
            new_password=(NEW_PASSWORD),
            additional_keyfile_paths=(unknown_keyfile_path,),
        )

    assert vault_path.read_bytes() == original_vault


def test_duplicate_keyfile_is_rejected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    original_vault = vault_path.read_bytes()

    with pytest.raises(
        KeyfileSetError,
        match="exactly once",
    ):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(primary_keyfile_path),
            current_password=(OLD_PASSWORD),
            new_password=(NEW_PASSWORD),
            additional_keyfile_paths=(primary_keyfile_path,),
        )

    assert vault_path.read_bytes() == original_vault


def test_new_password_must_differ(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    original_vault = vault_path.read_bytes()

    with pytest.raises(
        ValueError,
        match="must differ",
    ):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(primary_keyfile_path),
            current_password=(OLD_PASSWORD),
            new_password=OLD_PASSWORD,
        )

    assert vault_path.read_bytes() == original_vault


def test_wrong_current_password_does_not_modify_vault(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_vault(tmp_path)

    original_vault = vault_path.read_bytes()

    with pytest.raises(UnlockError):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(primary_keyfile_path),
            current_password=("incorrect password"),
            new_password=(NEW_PASSWORD),
        )

    assert vault_path.read_bytes() == original_vault
