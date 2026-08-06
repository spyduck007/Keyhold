"""End-to-end tests for recovery codes and USB restoration."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.errors import (
    RecoveryAlreadyConfiguredError,
    UnlockError,
)
from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.vault.creator import (
    create_vault,
)
from usb_vault.core.vault.operations import (
    add_file,
    extract_file,
)
from usb_vault.core.vault.recovery import (
    create_recovery_code,
    recover_usb_key,
    unlock_vault_with_recovery,
)
from usb_vault.core.vault.unlocker import (
    unlock_vault,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

PASSWORD = "correct horse battery staple"


def _create_paths(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
]:
    primary_directory = tmp_path / "primary-usb"
    primary_directory.mkdir()

    vault_path = tmp_path / "PrivateVault.vault"
    primary_keyfile_path = primary_directory / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )

    return (
        vault_path,
        primary_keyfile_path,
    )


def test_create_recovery_code_and_unlock_without_usb(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    result = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )

    assert not result.replaced_existing
    assert (
        read_vault_container(vault_path).header.find_recovery_slot(result.recovery_id) is not None
    )

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=PASSWORD,
        recovery_code=(result.recovery_code),
    ) as session:
        assert session.entry_count == 0

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    ) as session:
        assert session.entry_count == 0


def test_recovery_requires_correct_password_and_code(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    first = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )

    second_vault = tmp_path / "Second.vault"
    second_key = tmp_path / "second.authkey"
    create_vault(
        vault_path=second_vault,
        keyfile_path=second_key,
        password=PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )
    second = create_recovery_code(
        vault_path=second_vault,
        keyfile_path=second_key,
        password=PASSWORD,
    )

    with pytest.raises(
        UnlockError,
        match=(r"^Unable to unlock vault\.$"),
    ):
        unlock_vault_with_recovery(
            vault_path=vault_path,
            password="wrong password",
            recovery_code=(first.recovery_code),
        )

    with pytest.raises(
        UnlockError,
        match=(r"^Unable to unlock vault\.$"),
    ):
        unlock_vault_with_recovery(
            vault_path=vault_path,
            password=PASSWORD,
            recovery_code=(second.recovery_code),
        )

    with pytest.raises(
        UnlockError,
        match=(r"^Unable to unlock vault\.$"),
    ):
        unlock_vault_with_recovery(
            vault_path=vault_path,
            password=PASSWORD,
            recovery_code=("not a recovery code"),
        )


def test_existing_recovery_requires_explicit_rotation(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )
    original_vault = vault_path.read_bytes()

    with pytest.raises(RecoveryAlreadyConfiguredError):
        create_recovery_code(
            vault_path=vault_path,
            keyfile_path=(primary_keyfile_path),
            password=PASSWORD,
        )

    assert vault_path.read_bytes() == original_vault


def test_rotating_recovery_invalidates_old_code(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    old = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )
    new = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
        replace=True,
    )

    assert new.replaced_existing
    assert new.recovery_code != old.recovery_code

    with pytest.raises(UnlockError):
        unlock_vault_with_recovery(
            vault_path=vault_path,
            password=PASSWORD,
            recovery_code=(old.recovery_code),
        )

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=PASSWORD,
        recovery_code=(new.recovery_code),
    ) as session:
        assert session.entry_count == 0


def test_recover_usb_preserves_files_and_rotates_code(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    source_path = tmp_path / "notes.txt"
    output_path = tmp_path / "recovered-notes.txt"
    recovered_keyfile_path = tmp_path / "recovered-usb" / ".authkey"
    recovered_keyfile_path.parent.mkdir()
    source_contents = b"important encrypted notes\n"
    source_path.write_bytes(source_contents)

    add_file(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
        source_path=source_path,
    )
    old_recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )

    result = recover_usb_key(
        vault_path=vault_path,
        password=PASSWORD,
        recovery_code=(old_recovery.recovery_code),
        new_keyfile_path=(recovered_keyfile_path),
    )

    assert recovered_keyfile_path.is_file()
    assert not result.replaced_existing_keys

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=(recovered_keyfile_path),
        password=PASSWORD,
    ) as session:
        assert session.entry_count == 1

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    ) as session:
        assert session.entry_count == 1

    with pytest.raises(UnlockError):
        unlock_vault_with_recovery(
            vault_path=vault_path,
            password=PASSWORD,
            recovery_code=(old_recovery.recovery_code),
        )

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=PASSWORD,
        recovery_code=(result.recovery_code),
    ) as session:
        assert session.entry_count == 1

    extract_file(
        vault_path=vault_path,
        keyfile_path=(recovered_keyfile_path),
        password=PASSWORD,
        stored_name="notes.txt",
        destination_path=(output_path),
    )

    assert output_path.read_bytes() == source_contents


def test_recover_usb_can_revoke_all_previous_keys(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    recovered_directory = tmp_path / "recovered-usb"
    recovered_directory.mkdir()
    recovered_keyfile_path = recovered_directory / ".authkey"

    recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )

    result = recover_usb_key(
        vault_path=vault_path,
        password=PASSWORD,
        recovery_code=(recovery.recovery_code),
        new_keyfile_path=(recovered_keyfile_path),
        replace_existing_keys=True,
    )

    assert result.replaced_existing_keys

    with pytest.raises(UnlockError):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=(primary_keyfile_path),
            password=PASSWORD,
        )

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=(recovered_keyfile_path),
        password=PASSWORD,
    ) as session:
        assert session.entry_count == 0


def test_existing_recovered_key_destination_is_preserved(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        primary_keyfile_path,
    ) = _create_paths(tmp_path)

    recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=(primary_keyfile_path),
        password=PASSWORD,
    )
    destination = tmp_path / "existing.authkey"
    destination.write_bytes(b"existing data")
    original_vault = vault_path.read_bytes()

    with pytest.raises(FileExistsError):
        recover_usb_key(
            vault_path=vault_path,
            password=PASSWORD,
            recovery_code=(recovery.recovery_code),
            new_keyfile_path=(destination),
        )

    assert destination.read_bytes() == b"existing data"
    assert vault_path.read_bytes() == original_vault
