"""Tests for combining the password key and USB secret."""

import pytest

from usb_vault.core.crypto.key_derivation import (
    KEY_ENCRYPTION_KEY_LENGTH,
    derive_key_encryption_key,
)

PASSWORD_KEY_A = b"P" * 32
PASSWORD_KEY_B = b"Q" * 32
USB_SECRET_A = b"U" * 32
USB_SECRET_B = b"V" * 32


def test_same_inputs_produce_same_key_encryption_key() -> None:
    first = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_A,
    )

    second = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_A,
    )

    assert first == second
    assert len(first) == KEY_ENCRYPTION_KEY_LENGTH


def test_different_password_key_changes_output() -> None:
    first = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_A,
    )

    second = derive_key_encryption_key(
        PASSWORD_KEY_B,
        USB_SECRET_A,
    )

    assert first != second


def test_different_usb_secret_changes_output() -> None:
    first = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_A,
    )

    second = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_B,
    )

    assert first != second


def test_different_context_changes_output() -> None:
    first = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_A,
    )

    second = derive_key_encryption_key(
        PASSWORD_KEY_A,
        USB_SECRET_A,
        context=b"USB Vault Different Purpose v1",
    )

    assert first != second


@pytest.mark.parametrize(
    ("password_key", "usb_secret"),
    [
        (b"short", USB_SECRET_A),
        (PASSWORD_KEY_A, b"short"),
    ],
)
def test_incorrect_input_lengths_are_rejected(
    password_key: bytes,
    usb_secret: bytes,
) -> None:
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        derive_key_encryption_key(
            password_key,
            usb_secret,
        )
