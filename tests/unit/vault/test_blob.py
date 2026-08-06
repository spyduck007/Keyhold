"""Tests for independently encrypted file blobs."""

import pytest

from usb_vault.core.crypto.random import generate_master_key
from usb_vault.core.errors import UnlockError
from usb_vault.core.storage.format import VAULT_ID_LENGTH
from usb_vault.core.vault.blob import (
    BLOB_ID_LENGTH,
    EncryptedBlob,
    decrypt_blob,
    encrypt_blob,
)

VAULT_ID = b"V" * VAULT_ID_LENGTH


def test_blob_round_trip() -> None:
    master_key = generate_master_key()
    plaintext = b"file contents\x00with binary data"

    blob = encrypt_blob(
        plaintext,
        master_key,
        vault_id=VAULT_ID,
    )

    assert len(blob.blob_id) == BLOB_ID_LENGTH
    assert (
        decrypt_blob(
            blob,
            master_key,
            vault_id=VAULT_ID,
        )
        == plaintext
    )


def test_same_plaintext_uses_fresh_identifiers() -> None:
    master_key = generate_master_key()

    first = encrypt_blob(
        b"same",
        master_key,
        vault_id=VAULT_ID,
    )
    second = encrypt_blob(
        b"same",
        master_key,
        vault_id=VAULT_ID,
    )

    assert first.blob_id != second.blob_id
    assert first.payload.nonce != second.payload.nonce
    assert first.payload.ciphertext != second.payload.ciphertext


def test_blob_cannot_move_to_another_vault() -> None:
    master_key = generate_master_key()
    blob = encrypt_blob(
        b"secret",
        master_key,
        vault_id=VAULT_ID,
    )

    with pytest.raises(UnlockError):
        decrypt_blob(
            blob,
            master_key,
            vault_id=(b"X" * VAULT_ID_LENGTH),
        )


def test_blob_id_tampering_is_detected() -> None:
    master_key = generate_master_key()
    blob = encrypt_blob(
        b"secret",
        master_key,
        vault_id=VAULT_ID,
    )
    modified = EncryptedBlob(
        blob_id=(b"X" * BLOB_ID_LENGTH),
        payload=blob.payload,
    )

    with pytest.raises(UnlockError):
        decrypt_blob(
            modified,
            master_key,
            vault_id=VAULT_ID,
        )
