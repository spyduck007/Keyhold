"""Authenticated encryption for the vault master key."""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from usb_vault.core.crypto.key_derivation import (
    KEY_ENCRYPTION_KEY_LENGTH,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    MASTER_KEY_LENGTH,
    generate_aes_gcm_nonce,
)
from usb_vault.core.errors import UnlockError

MASTER_KEY_WRAP_AAD = b"USBVAULT|wrapped-master-key|v1"
AES_GCM_TAG_LENGTH = 16


@dataclass(frozen=True, slots=True)
class WrappedMasterKey:
    """The nonce and authenticated ciphertext stored in the vault header."""

    nonce: bytes
    ciphertext: bytes


def wrap_master_key(
    master_key: bytes,
    key_encryption_key: bytes,
) -> WrappedMasterKey:
    """Encrypt a master key with a fresh AES-GCM nonce."""
    _require_bytes_of_length(
        "master_key",
        master_key,
        MASTER_KEY_LENGTH,
    )
    _require_bytes_of_length(
        "key_encryption_key",
        key_encryption_key,
        KEY_ENCRYPTION_KEY_LENGTH,
    )

    nonce = generate_aes_gcm_nonce()

    ciphertext = AESGCM(key_encryption_key).encrypt(
        nonce,
        master_key,
        MASTER_KEY_WRAP_AAD,
    )

    return WrappedMasterKey(
        nonce=nonce,
        ciphertext=ciphertext,
    )


def unwrap_master_key(
    wrapped_master_key: WrappedMasterKey,
    key_encryption_key: bytes,
) -> bytes:
    """Decrypt a wrapped master key or raise one generic unlock error."""
    try:
        _require_bytes_of_length(
            "key_encryption_key",
            key_encryption_key,
            KEY_ENCRYPTION_KEY_LENGTH,
        )

        _require_bytes_of_length(
            "nonce",
            wrapped_master_key.nonce,
            AES_GCM_NONCE_LENGTH,
        )

        if not isinstance(wrapped_master_key.ciphertext, bytes):
            raise TypeError("ciphertext must be bytes")

        if len(wrapped_master_key.ciphertext) < AES_GCM_TAG_LENGTH:
            raise ValueError("ciphertext is too short")

        master_key = AESGCM(key_encryption_key).decrypt(
            wrapped_master_key.nonce,
            wrapped_master_key.ciphertext,
            MASTER_KEY_WRAP_AAD,
        )

        if len(master_key) != MASTER_KEY_LENGTH:
            raise ValueError("decrypted master key has an invalid length")

        return master_key

    except (InvalidTag, TypeError, ValueError):
        raise UnlockError from None


def _require_bytes_of_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
