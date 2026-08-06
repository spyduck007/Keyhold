"""Tests for authenticated master-key wrapping."""

import pytest

from usb_vault.core.crypto.encryption import (
    WrappedMasterKey,
    unwrap_master_key,
    wrap_master_key,
)
from usb_vault.core.crypto.random import generate_master_key
from usb_vault.core.errors import (
    GENERIC_UNLOCK_MESSAGE,
    UnlockError,
)

KEY_ENCRYPTION_KEY = b"K" * 32
WRONG_KEY_ENCRYPTION_KEY = b"W" * 32


def test_wrap_and_unwrap_master_key_round_trip() -> None:
    master_key = generate_master_key()

    wrapped = wrap_master_key(
        master_key,
        KEY_ENCRYPTION_KEY,
    )

    assert (
        unwrap_master_key(
            wrapped,
            KEY_ENCRYPTION_KEY,
        )
        == master_key
    )


def test_each_wrap_uses_a_fresh_nonce() -> None:
    master_key = generate_master_key()

    first = wrap_master_key(
        master_key,
        KEY_ENCRYPTION_KEY,
    )

    second = wrap_master_key(
        master_key,
        KEY_ENCRYPTION_KEY,
    )

    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext


def test_wrong_key_raises_generic_unlock_error() -> None:
    wrapped = wrap_master_key(
        generate_master_key(),
        KEY_ENCRYPTION_KEY,
    )

    with pytest.raises(UnlockError) as error:
        unwrap_master_key(
            wrapped,
            WRONG_KEY_ENCRYPTION_KEY,
        )

    assert str(error.value) == GENERIC_UNLOCK_MESSAGE


def test_corrupted_ciphertext_raises_generic_unlock_error() -> None:
    wrapped = wrap_master_key(
        generate_master_key(),
        KEY_ENCRYPTION_KEY,
    )

    corrupted_ciphertext = bytearray(wrapped.ciphertext)
    corrupted_ciphertext[-1] ^= 0x01

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
            KEY_ENCRYPTION_KEY,
        )


def test_corrupted_nonce_raises_generic_unlock_error() -> None:
    wrapped = wrap_master_key(
        generate_master_key(),
        KEY_ENCRYPTION_KEY,
    )

    corrupted_nonce = bytearray(wrapped.nonce)
    corrupted_nonce[0] ^= 0x01

    corrupted = WrappedMasterKey(
        nonce=bytes(corrupted_nonce),
        ciphertext=wrapped.ciphertext,
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        unwrap_master_key(
            corrupted,
            KEY_ENCRYPTION_KEY,
        )
