"""Tests for password rotation when recovery is configured."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.errors import (
    KeyfileSetError,
    UnlockError,
)
from usb_vault.core.vault.creator import (
    create_vault,
)
from usb_vault.core.vault.password_management import (
    change_vault_password,
)
from usb_vault.core.vault.recovery import (
    create_recovery_code,
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

OLD_PASSWORD = "old correct password"
NEW_PASSWORD = "new correct password"


def _create_vault(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
]:
    vault_path = tmp_path / "PrivateVault.vault"
    keyfile_path = tmp_path / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=OLD_PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )

    return (
        vault_path,
        keyfile_path,
    )


def test_password_change_rewraps_recovery_slot(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_vault(tmp_path)

    recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=OLD_PASSWORD,
    )

    result = change_vault_password(
        vault_path=vault_path,
        current_keyfile_path=(keyfile_path),
        current_password=(OLD_PASSWORD),
        new_password=NEW_PASSWORD,
        recovery_code=(recovery.recovery_code),
    )

    assert result.recovery_updated

    with pytest.raises(UnlockError):
        unlock_vault_with_recovery(
            vault_path=vault_path,
            password=OLD_PASSWORD,
            recovery_code=(recovery.recovery_code),
        )

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=NEW_PASSWORD,
        recovery_code=(recovery.recovery_code),
    ) as session:
        assert session.entry_count == 0

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


def test_password_change_requires_recovery_code(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_vault(tmp_path)

    recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=OLD_PASSWORD,
    )
    original_vault = vault_path.read_bytes()

    with pytest.raises(
        KeyfileSetError,
        match="current recovery code",
    ):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(keyfile_path),
            current_password=(OLD_PASSWORD),
            new_password=(NEW_PASSWORD),
        )

    assert vault_path.read_bytes() == original_vault

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=OLD_PASSWORD,
        recovery_code=(recovery.recovery_code),
    ) as session:
        assert session.entry_count == 0


def test_wrong_recovery_code_does_not_change_password(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_vault(tmp_path)

    recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=OLD_PASSWORD,
    )

    other_vault = tmp_path / "Other.vault"
    other_key = tmp_path / "other.authkey"
    create_vault(
        vault_path=other_vault,
        keyfile_path=other_key,
        password=OLD_PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )
    other_recovery = create_recovery_code(
        vault_path=other_vault,
        keyfile_path=other_key,
        password=OLD_PASSWORD,
    )
    original_vault = vault_path.read_bytes()

    with pytest.raises(UnlockError):
        change_vault_password(
            vault_path=vault_path,
            current_keyfile_path=(keyfile_path),
            current_password=(OLD_PASSWORD),
            new_password=(NEW_PASSWORD),
            recovery_code=(other_recovery.recovery_code),
        )

    assert vault_path.read_bytes() == original_vault

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=OLD_PASSWORD,
        recovery_code=(recovery.recovery_code),
    ) as session:
        assert session.entry_count == 0
