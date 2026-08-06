"""Operating-system-backed random value generation."""

from __future__ import annotations

import secrets

ARGON2_SALT_LENGTH = 16
USB_SECRET_LENGTH = 32
MASTER_KEY_LENGTH = 32
AES_GCM_NONCE_LENGTH = 12


def secure_random_bytes(length: int) -> bytes:
    """Return ``length`` bytes from Python's OS-backed CSPRNG."""
    if not isinstance(length, int):
        raise TypeError("length must be an integer")

    if length <= 0:
        raise ValueError("length must be greater than zero")

    return secrets.token_bytes(length)


def generate_argon2_salt() -> bytes:
    """Generate a new vault-specific Argon2 salt."""
    return secure_random_bytes(ARGON2_SALT_LENGTH)


def generate_usb_secret() -> bytes:
    """Generate the secret that will eventually be stored on the USB drive."""
    return secure_random_bytes(USB_SECRET_LENGTH)


def generate_master_key() -> bytes:
    """Generate the random key used to encrypt vault contents."""
    return secure_random_bytes(MASTER_KEY_LENGTH)


def generate_aes_gcm_nonce() -> bytes:
    """Generate a fresh nonce for AES-GCM."""
    return secure_random_bytes(AES_GCM_NONCE_LENGTH)
