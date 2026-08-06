"""Authenticated encryption for vault payloads."""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from usb_vault.core.crypto.encryption import AES_GCM_TAG_LENGTH
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    MASTER_KEY_LENGTH,
    generate_aes_gcm_nonce,
)
from usb_vault.core.errors import UnlockError


@dataclass(frozen=True, slots=True)
class EncryptedPayload:
    """An AES-GCM nonce and its authenticated ciphertext."""

    nonce: bytes
    ciphertext: bytes

    def __post_init__(self) -> None:
        _require_bytes_length(
            "nonce",
            self.nonce,
            AES_GCM_NONCE_LENGTH,
        )

        if not isinstance(self.ciphertext, bytes):
            raise TypeError("ciphertext must be bytes")

        if len(self.ciphertext) < AES_GCM_TAG_LENGTH:
            raise ValueError("ciphertext is too short")


def encrypt_payload(
    plaintext: bytes,
    master_key: bytes,
    *,
    associated_data: bytes,
) -> EncryptedPayload:
    """Encrypt bytes using the vault master key and a fresh nonce."""
    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes")

    _require_bytes_length(
        "master_key",
        master_key,
        MASTER_KEY_LENGTH,
    )
    _require_associated_data(associated_data)

    nonce = generate_aes_gcm_nonce()
    ciphertext = AESGCM(master_key).encrypt(
        nonce,
        plaintext,
        associated_data,
    )

    return EncryptedPayload(
        nonce=nonce,
        ciphertext=ciphertext,
    )


def decrypt_payload(
    payload: EncryptedPayload,
    master_key: bytes,
    *,
    associated_data: bytes,
) -> bytes:
    """Decrypt authenticated payload bytes or raise a generic unlock error."""
    try:
        if not isinstance(payload, EncryptedPayload):
            raise TypeError("payload must be EncryptedPayload")

        _require_bytes_length(
            "master_key",
            master_key,
            MASTER_KEY_LENGTH,
        )
        _require_associated_data(associated_data)

        return AESGCM(master_key).decrypt(
            payload.nonce,
            payload.ciphertext,
            associated_data,
        )
    except (InvalidTag, TypeError, ValueError):
        raise UnlockError from None


def _require_associated_data(value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError("associated_data must be bytes")

    if not value:
        raise ValueError("associated_data must not be empty")


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
