"""Integration tests for the desktop Security Center backend."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.errors import (
    UnlockError,
)
from usb_vault.core.vault.creator import (
    create_vault,
)
from usb_vault.core.vault.operations import (
    add_file,
)
from usb_vault.core.vault.recovery import (
    create_recovery_code,
    unlock_vault_with_recovery,
)
from usb_vault.core.vault.unlocker import (
    unlock_vault,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)
from usb_vault.ui.security_backend import (
    CoreVaultSecurityBackend,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

OLD_PASSWORD = "old correct password"
NEW_PASSWORD = "new correct password"


def test_security_backend_manages_keys_and_password(
    tmp_path: Path,
) -> None:
    primary_directory = tmp_path / "primary-usb"
    backup_directory = tmp_path / "backup-usb"
    primary_directory.mkdir()
    backup_directory.mkdir()

    vault_path = tmp_path / "Private.vault"
    primary_keyfile = primary_directory / ".authkey"
    backup_keyfile = backup_directory / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=primary_keyfile,
        password=OLD_PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )

    source_path = tmp_path / "notes.txt"
    source_path.write_text(
        "security center test\n",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=primary_keyfile,
        password=OLD_PASSWORD,
        source_path=source_path,
    )

    recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=primary_keyfile,
        password=OLD_PASSWORD,
    )

    original_vault = UnlockedVault.create(
        vault_path=vault_path,
        keyfile_path=primary_keyfile,
        password=OLD_PASSWORD,
    )
    updated_vault: UnlockedVault | None = None

    backend = CoreVaultSecurityBackend()

    try:
        initial = backend.snapshot(original_vault)

        assert len(initial.keys) == 1
        assert initial.recovery_configured

        added = backend.add_key(
            original_vault,
            backup_keyfile,
        )

        assert backup_keyfile.is_file()
        assert not added.is_current

        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=backup_keyfile,
            password=OLD_PASSWORD,
        ) as session:
            assert session.entry_count == 1

        after_add = backend.snapshot(original_vault)

        assert len(after_add.keys) == 2
        assert after_add.additional_keyfile_count == 1

        changed = backend.change_password(
            original_vault,
            current_password=OLD_PASSWORD,
            new_password=NEW_PASSWORD,
            additional_keyfile_paths=(backup_keyfile,),
            recovery_code=(recovery.recovery_code),
        )
        updated_vault = changed.vault

        assert changed.key_count == 2
        assert changed.recovery_updated
        assert [entry.name for entry in changed.entries] == [
            "notes.txt",
        ]

        with pytest.raises(UnlockError):
            unlock_vault(
                vault_path=vault_path,
                keyfile_path=primary_keyfile,
                password=OLD_PASSWORD,
            )

        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=primary_keyfile,
            password=NEW_PASSWORD,
        ) as session:
            assert session.entry_count == 1

        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=backup_keyfile,
            password=NEW_PASSWORD,
        ) as session:
            assert session.entry_count == 1

        with unlock_vault_with_recovery(
            vault_path=vault_path,
            password=NEW_PASSWORD,
            recovery_code=(recovery.recovery_code),
        ) as session:
            assert session.entry_count == 1

        backend.revoke_key(
            updated_vault,
            added.key_id_hex,
        )

        with pytest.raises(UnlockError):
            unlock_vault(
                vault_path=vault_path,
                keyfile_path=backup_keyfile,
                password=NEW_PASSWORD,
            )

        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=primary_keyfile,
            password=NEW_PASSWORD,
        ) as session:
            assert session.entry_count == 1
    finally:
        original_vault.close()

        if updated_vault is not None:
            updated_vault.close()
