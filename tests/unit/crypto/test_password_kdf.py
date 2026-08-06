"""Tests for Argon2id password key derivation."""

import pytest

from usb_vault.core.crypto.password_kdf import (
    PASSWORD_KEY_LENGTH,
    Argon2Parameters,
    derive_password_key,
)

# These deliberately weak parameters are used only to make tests fast.
# They must never become production defaults.
TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

SALT_A = b"A" * 16
SALT_B = b"B" * 16


def test_same_password_salt_and_parameters_produce_same_key() -> None:
    first = derive_password_key(
        "correct horse battery staple",
        SALT_A,
        TEST_PARAMETERS,
    )

    second = derive_password_key(
        "correct horse battery staple",
        SALT_A,
        TEST_PARAMETERS,
    )

    assert first == second
    assert len(first) == PASSWORD_KEY_LENGTH


def test_different_password_produces_different_key() -> None:
    first = derive_password_key(
        "first password",
        SALT_A,
        TEST_PARAMETERS,
    )

    second = derive_password_key(
        "second password",
        SALT_A,
        TEST_PARAMETERS,
    )

    assert first != second


def test_different_salt_produces_different_key() -> None:
    first = derive_password_key(
        "same password",
        SALT_A,
        TEST_PARAMETERS,
    )

    second = derive_password_key(
        "same password",
        SALT_B,
        TEST_PARAMETERS,
    )

    assert first != second


def test_password_accepts_mutable_bytes_like_input() -> None:
    password = bytearray(b"test password")

    result = derive_password_key(
        password,
        SALT_A,
        TEST_PARAMETERS,
    )

    assert len(result) == PASSWORD_KEY_LENGTH


def test_empty_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        derive_password_key(
            "",
            SALT_A,
            TEST_PARAMETERS,
        )


def test_short_salt_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 16 bytes"):
        derive_password_key(
            "password",
            b"too short",
            TEST_PARAMETERS,
        )
