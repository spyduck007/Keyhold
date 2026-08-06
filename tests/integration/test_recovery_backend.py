"""Integration tests for the desktop recovery bridge."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.errors import UnlockError
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
from usb_vault.ui.recovery_backend import (
    CoreVaultRecoveryBackend,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

PASSWORD = "correct horse battery staple"


def test_recovery_backend_restores_and_opens_vault(
    tmp_path: Path,
) -> None:
    primary_usb = tmp_path / "primary-usb"
    replacement_usb = tmp_path / "replacement-usb"
    primary_usb.mkdir()
    replacement_usb.mkdir()

    vault_path = tmp_path / "Private.vault"
    original_keyfile = primary_usb / ".authkey"
    replacement_keyfile = replacement_usb / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=original_keyfile,
        password=PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )

    source_path = tmp_path / "notes.txt"
    source_path.write_text(
        "important recovery test\n",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=original_keyfile,
        password=PASSWORD,
        source_path=source_path,
    )

    old_recovery = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=original_keyfile,
        password=PASSWORD,
    )

    backend = CoreVaultRecoveryBackend()

    recovered = backend.recover_vault(
        vault_path=vault_path,
        new_keyfile_path=(replacement_keyfile),
        password=PASSWORD,
        recovery_code=(old_recovery.recovery_code),
        replace_existing_keys=True,
    )

    try:
        assert replacement_keyfile.is_file()
        assert recovered.recovery_code != old_recovery.recovery_code
        assert recovered.replaced_existing_keys
        assert [entry.name for entry in recovered.entries] == [
            "notes.txt",
        ]

        with pytest.raises(UnlockError):
            unlock_vault(
                vault_path=vault_path,
                keyfile_path=(original_keyfile),
                password=PASSWORD,
            )

        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=(replacement_keyfile),
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
            recovery_code=(recovered.recovery_code),
        ) as session:
            assert session.entry_count == 1
    finally:
        recovered.vault.close()
