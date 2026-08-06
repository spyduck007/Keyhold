"""End-to-end tests for the initial two-factor cryptographic flow."""

import pytest

from usb_vault.core.crypto.encryption import (
    WrappedMasterKey,
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
    generate_usb_secret,
)
from usb_vault.core.errors import UnlockError

# Deliberately inexpensive test-only settings.
TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def _derive_unlock_key(
    password: str,
    salt: bytes,
    usb_secret: bytes,
) -> bytes:
    password_key = derive_password_key(
        password,
        salt,
        TEST_PARAMETERS,
    )

    return derive_key_encryption_key(
        password_key,
        usb_secret,
    )


def test_master_key_requires_correct_password_and_usb_secret() -> None:
    password = "a long test passphrase"
    salt = generate_argon2_salt()
    usb_secret = generate_usb_secret()
    master_key = generate_master_key()

    creation_key = _derive_unlock_key(
        password,
        salt,
        usb_secret,
    )

    wrapped_master_key = wrap_master_key(
        master_key,
        creation_key,
    )

    unlock_key = _derive_unlock_key(
        password,
        salt,
        usb_secret,
    )

    assert (
        unwrap_master_key(
            wrapped_master_key,
            unlock_key,
        )
        == master_key
    )


def test_wrong_password_cannot_unwrap_master_key() -> None:
    salt = generate_argon2_salt()
    usb_secret = generate_usb_secret()
    master_key = generate_master_key()

    wrapped = wrap_master_key(
        master_key,
        _derive_unlock_key(
            "correct password",
            salt,
            usb_secret,
        ),
    )

    wrong_password_key = _derive_unlock_key(
        "wrong password",
        salt,
        usb_secret,
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unwrap_master_key(
            wrapped,
            wrong_password_key,
        )


def test_wrong_usb_secret_cannot_unwrap_master_key() -> None:
    password = "correct password"
    salt = generate_argon2_salt()
    correct_usb_secret = generate_usb_secret()
    wrong_usb_secret = generate_usb_secret()
    master_key = generate_master_key()

    wrapped = wrap_master_key(
        master_key,
        _derive_unlock_key(
            password,
            salt,
            correct_usb_secret,
        ),
    )

    wrong_usb_key = _derive_unlock_key(
        password,
        salt,
        wrong_usb_secret,
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unwrap_master_key(
            wrapped,
            wrong_usb_key,
        )


def test_corrupted_wrapped_master_key_is_rejected() -> None:
    password = "correct password"
    salt = generate_argon2_salt()
    usb_secret = generate_usb_secret()
    master_key = generate_master_key()

    unlock_key = _derive_unlock_key(
        password,
        salt,
        usb_secret,
    )

    wrapped = wrap_master_key(
        master_key,
        unlock_key,
    )

    corrupted_ciphertext = bytearray(wrapped.ciphertext)
    corrupted_ciphertext[len(corrupted_ciphertext) // 2] ^= 0x01

    corrupted = WrappedMasterKey(
        nonce=wrapped.nonce,
        ciphertext=bytes(corrupted_ciphertext),
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unwrap_master_key(
            corrupted,
            unlock_key,
        )
