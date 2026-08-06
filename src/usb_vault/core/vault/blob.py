"""Encrypted file-blob records stored inside a vault container."""

from __future__ import annotations

from dataclasses import dataclass

from usb_vault.core.crypto.encryption import AES_GCM_TAG_LENGTH
from usb_vault.core.crypto.payload_encryption import (
    EncryptedPayload,
    decrypt_payload,
    encrypt_payload,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    secure_random_bytes,
)
from usb_vault.core.storage.format import VAULT_ID_LENGTH

BLOB_ID_LENGTH = 16

# The current prototype loads each file into memory.
# Streaming support will replace this limit later.
MAX_BLOB_PLAINTEXT_LENGTH = 67_108_864
MAX_BLOB_CIPHERTEXT_LENGTH = MAX_BLOB_PLAINTEXT_LENGTH + AES_GCM_TAG_LENGTH

BLOB_AAD_PREFIX = b"USBVAULT|file-blob|v1|"


@dataclass(frozen=True, slots=True)
class EncryptedBlob:
    """One independently encrypted file payload."""

    blob_id: bytes
    payload: EncryptedPayload

    def __post_init__(self) -> None:
        _require_bytes_length(
            "blob_id",
            self.blob_id,
            BLOB_ID_LENGTH,
        )

        if not isinstance(
            self.payload,
            EncryptedPayload,
        ):
            raise TypeError("payload must be EncryptedPayload")

        if len(self.payload.nonce) != AES_GCM_NONCE_LENGTH:
            raise ValueError("encrypted blob nonce has an invalid length")

        if len(self.payload.ciphertext) > MAX_BLOB_CIPHERTEXT_LENGTH:
            raise ValueError("encrypted blob is too large")


def encrypt_blob(
    plaintext: bytes,
    master_key: bytes,
    *,
    vault_id: bytes,
    blob_id: bytes | None = None,
) -> EncryptedBlob:
    """Encrypt and bind a file to its vault and blob identifiers."""
    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes")

    if len(plaintext) > MAX_BLOB_PLAINTEXT_LENGTH:
        raise ValueError("plaintext blob is too large")

    selected_blob_id = blob_id if blob_id is not None else secure_random_bytes(BLOB_ID_LENGTH)

    _require_bytes_length(
        "blob_id",
        selected_blob_id,
        BLOB_ID_LENGTH,
    )

    return EncryptedBlob(
        blob_id=selected_blob_id,
        payload=encrypt_payload(
            plaintext,
            master_key,
            associated_data=blob_associated_data(
                vault_id,
                selected_blob_id,
            ),
        ),
    )


def decrypt_blob(
    blob: EncryptedBlob,
    master_key: bytes,
    *,
    vault_id: bytes,
) -> bytes:
    """Decrypt one authenticated file blob."""
    if not isinstance(
        blob,
        EncryptedBlob,
    ):
        raise TypeError("blob must be EncryptedBlob")

    plaintext = decrypt_payload(
        blob.payload,
        master_key,
        associated_data=blob_associated_data(
            vault_id,
            blob.blob_id,
        ),
    )

    if len(plaintext) > MAX_BLOB_PLAINTEXT_LENGTH:
        raise ValueError("decrypted blob is too large")

    return plaintext


def blob_associated_data(
    vault_id: bytes,
    blob_id: bytes,
) -> bytes:
    """Prevent a blob from being substituted into another vault."""
    _require_bytes_length(
        "vault_id",
        vault_id,
        VAULT_ID_LENGTH,
    )
    _require_bytes_length(
        "blob_id",
        blob_id,
        BLOB_ID_LENGTH,
    )

    return BLOB_AAD_PREFIX + vault_id + blob_id


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
