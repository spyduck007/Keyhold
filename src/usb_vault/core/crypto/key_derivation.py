"""Derive the key used to wrap and unwrap the vault master key."""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from usb_vault.core.crypto.password_kdf import PASSWORD_KEY_LENGTH
from usb_vault.core.crypto.random import USB_SECRET_LENGTH

KEY_ENCRYPTION_KEY_LENGTH = 32
MASTER_KEY_WRAP_CONTEXT = b"USB Vault Master Key Wrapping v1"


def derive_key_encryption_key(
    password_key: bytes,
    usb_secret: bytes,
    *,
    context: bytes = MASTER_KEY_WRAP_CONTEXT,
) -> bytes:
    """Combine the password key and USB secret using HKDF-SHA256."""
    _require_bytes_of_length(
        "password_key",
        password_key,
        PASSWORD_KEY_LENGTH,
    )
    _require_bytes_of_length(
        "usb_secret",
        usb_secret,
        USB_SECRET_LENGTH,
    )

    if not isinstance(context, bytes):
        raise TypeError("context must be bytes")

    if not context:
        raise ValueError("context must not be empty")

    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_ENCRYPTION_KEY_LENGTH,
        salt=usb_secret,
        info=context,
    ).derive(password_key)


def _require_bytes_of_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
