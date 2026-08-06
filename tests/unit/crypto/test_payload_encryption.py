"""Tests for authenticated vault-payload encryption."""

import pytest

from usb_vault.core.crypto.payload_encryption import (
    EncryptedPayload,
    decrypt_payload,
    encrypt_payload,
)
from usb_vault.core.crypto.random import generate_master_key
from usb_vault.core.errors import UnlockError

AAD = b"USBVAULT|test-payload|v1"


def test_payload_round_trip() -> None:
    master_key = generate_master_key()
    plaintext = b"encrypted manifest contents"

    encrypted = encrypt_payload(
        plaintext,
        master_key,
        associated_data=AAD,
    )

    assert (
        decrypt_payload(
            encrypted,
            master_key,
            associated_data=AAD,
        )
        == plaintext
    )


def test_each_payload_encryption_uses_a_fresh_nonce() -> None:
    master_key = generate_master_key()

    first = encrypt_payload(
        b"same plaintext",
        master_key,
        associated_data=AAD,
    )
    second = encrypt_payload(
        b"same plaintext",
        master_key,
        associated_data=AAD,
    )

    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext


def test_wrong_master_key_is_rejected() -> None:
    encrypted = encrypt_payload(
        b"secret",
        generate_master_key(),
        associated_data=AAD,
    )

    with pytest.raises(
        UnlockError,
        match=r"^Unable to unlock vault\.$",
    ):
        decrypt_payload(
            encrypted,
            generate_master_key(),
            associated_data=AAD,
        )


def test_wrong_associated_data_is_rejected() -> None:
    master_key = generate_master_key()
    encrypted = encrypt_payload(
        b"secret",
        master_key,
        associated_data=AAD,
    )

    with pytest.raises(UnlockError):
        decrypt_payload(
            encrypted,
            master_key,
            associated_data=b"different context",
        )


def test_modified_ciphertext_is_rejected() -> None:
    master_key = generate_master_key()
    encrypted = encrypt_payload(
        b"secret",
        master_key,
        associated_data=AAD,
    )
    modified = bytearray(encrypted.ciphertext)
    modified[0] ^= 0x01

    with pytest.raises(UnlockError):
        decrypt_payload(
            EncryptedPayload(
                nonce=encrypted.nonce,
                ciphertext=bytes(modified),
            ),
            master_key,
            associated_data=AAD,
        )
