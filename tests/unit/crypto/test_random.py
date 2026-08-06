"""Tests for operating-system-backed random generation."""

import pytest

from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    ARGON2_SALT_LENGTH,
    MASTER_KEY_LENGTH,
    USB_SECRET_LENGTH,
    generate_aes_gcm_nonce,
    generate_argon2_salt,
    generate_master_key,
    generate_usb_secret,
    secure_random_bytes,
)


def test_secure_random_bytes_returns_requested_length() -> None:
    assert len(secure_random_bytes(48)) == 48


def test_separate_random_calls_return_different_values() -> None:
    assert secure_random_bytes(32) != secure_random_bytes(32)


@pytest.mark.parametrize("length", [0, -1, -100])
def test_secure_random_bytes_rejects_non_positive_length(
    length: int,
) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        secure_random_bytes(length)


def test_secure_random_bytes_rejects_non_integer_length() -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        secure_random_bytes(3.5)  # type: ignore[arg-type]


def test_named_generators_return_expected_lengths() -> None:
    assert len(generate_argon2_salt()) == ARGON2_SALT_LENGTH
    assert len(generate_usb_secret()) == USB_SECRET_LENGTH
    assert len(generate_master_key()) == MASTER_KEY_LENGTH
    assert len(generate_aes_gcm_nonce()) == AES_GCM_NONCE_LENGTH
