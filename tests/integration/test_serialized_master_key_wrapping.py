"""End-to-end test for serialized keyfiles and vault headers."""

import pytest

from usb_vault.core.crypto.encryption import (
    unwrap_master_key,
    wrap_master_key,
)
from usb_vault.core.crypto.key_derivation import (
    derive_key_encryption_key,
)
from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
    derive_password_key,
)
from usb_vault.core.crypto.random import (
    generate_argon2_salt,
    generate_master_key,
)
from usb_vault.core.errors import UnlockError
from usb_vault.core.keys.keyfile import (
    UsbKeyfile,
    create_usb_keyfile,
)
from usb_vault.core.storage.format import (
    VaultHeader,
    create_initial_vault_header,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def _derive_unlock_key(
    password: str,
    keyfile: UsbKeyfile,
    header: VaultHeader,
) -> bytes:
    password_key = derive_password_key(
        password,
        header.argon2_salt,
        header.argon2_parameters,
    )

    return derive_key_encryption_key(
        password_key,
        keyfile.secret,
    )


def test_serialized_keyfile_and_header_unlock_master_key() -> None:
    password = "correct horse battery staple"

    keyfile = create_usb_keyfile()
    salt = generate_argon2_salt()
    master_key = generate_master_key()

    password_key = derive_password_key(
        password,
        salt,
        TEST_PARAMETERS,
    )
    key_encryption_key = derive_key_encryption_key(
        password_key,
        keyfile.secret,
    )
    wrapped = wrap_master_key(
        master_key,
        key_encryption_key,
    )

    header = create_initial_vault_header(
        argon2_salt=salt,
        argon2_parameters=TEST_PARAMETERS,
        key_id=keyfile.key_id,
        wrapped_master_key=wrapped,
    )

    loaded_keyfile = UsbKeyfile.from_bytes(keyfile.to_bytes())
    loaded_header = VaultHeader.from_bytes(header.to_bytes())

    slot = loaded_header.find_password_usb_slot(loaded_keyfile.key_id)

    assert slot is not None

    loaded_unlock_key = _derive_unlock_key(
        password,
        loaded_keyfile,
        loaded_header,
    )

    assert (
        unwrap_master_key(
            slot.wrapped_master_key,
            loaded_unlock_key,
        )
        == master_key
    )


def test_different_serialized_keyfile_cannot_unlock_master_key() -> None:
    password = "correct horse battery staple"

    correct_keyfile = create_usb_keyfile()
    wrong_keyfile = create_usb_keyfile()
    salt = generate_argon2_salt()
    master_key = generate_master_key()

    password_key = derive_password_key(
        password,
        salt,
        TEST_PARAMETERS,
    )
    key_encryption_key = derive_key_encryption_key(
        password_key,
        correct_keyfile.secret,
    )
    wrapped = wrap_master_key(
        master_key,
        key_encryption_key,
    )

    header = create_initial_vault_header(
        argon2_salt=salt,
        argon2_parameters=TEST_PARAMETERS,
        key_id=correct_keyfile.key_id,
        wrapped_master_key=wrapped,
    )

    loaded_header = VaultHeader.from_bytes(header.to_bytes())

    assert loaded_header.find_password_usb_slot(wrong_keyfile.key_id) is None

    wrong_unlock_key = _derive_unlock_key(
        password,
        wrong_keyfile,
        loaded_header,
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unwrap_master_key(
            loaded_header.key_slots[0].wrapped_master_key,
            wrong_unlock_key,
        )
