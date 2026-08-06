"""Printable high-entropy recovery credentials."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from usb_vault.core.crypto.key_derivation import (
    KEY_ENCRYPTION_KEY_LENGTH,
)
from usb_vault.core.crypto.password_kdf import PASSWORD_KEY_LENGTH
from usb_vault.core.crypto.random import secure_random_bytes

RECOVERY_CODE_PREFIX = "UVR1"
RECOVERY_ID_LENGTH = 16
RECOVERY_SECRET_LENGTH = 24
RECOVERY_PAYLOAD_LENGTH = RECOVERY_ID_LENGTH + RECOVERY_SECRET_LENGTH
RECOVERY_ENCODED_LENGTH = 64
RECOVERY_GROUP_LENGTH = 4
RECOVERY_KEY_CONTEXT = b"USB Vault Password Recovery v1"

_BASE32_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


@dataclass(frozen=True, slots=True)
class RecoveryCredential:
    """A public recovery identifier and a high-entropy secret."""

    recovery_id: bytes
    secret: bytes

    def __post_init__(self) -> None:
        _require_bytes_length(
            "recovery_id",
            self.recovery_id,
            RECOVERY_ID_LENGTH,
        )
        _require_bytes_length(
            "secret",
            self.secret,
            RECOVERY_SECRET_LENGTH,
        )

    def to_code(self) -> str:
        """Return a printable, grouped recovery code."""
        return format_recovery_code(self)


def create_recovery_credential() -> RecoveryCredential:
    """Generate an independently random recovery credential."""
    return RecoveryCredential(
        recovery_id=secure_random_bytes(RECOVERY_ID_LENGTH),
        secret=secure_random_bytes(RECOVERY_SECRET_LENGTH),
    )


def format_recovery_code(
    credential: RecoveryCredential,
) -> str:
    """Encode a recovery credential as grouped Base32 text."""
    if not isinstance(
        credential,
        RecoveryCredential,
    ):
        raise TypeError("credential must be RecoveryCredential")

    payload = credential.recovery_id + credential.secret
    encoded = base64.b32encode(payload).decode("ascii")

    if len(encoded) != RECOVERY_ENCODED_LENGTH:
        raise RuntimeError("unexpected recovery-code encoding length")

    groups = (
        encoded[index : index + RECOVERY_GROUP_LENGTH]
        for index in range(
            0,
            len(encoded),
            RECOVERY_GROUP_LENGTH,
        )
    )

    return f"{RECOVERY_CODE_PREFIX}-" + "-".join(groups)


def parse_recovery_code(
    value: str,
) -> RecoveryCredential:
    """Parse a recovery code while tolerating spaces and hyphens."""
    if not isinstance(value, str):
        raise TypeError("recovery code must be a string")

    compact = "".join(
        character
        for character in value.upper()
        if character
        not in {
            "-",
            " ",
            "\t",
            "\r",
            "\n",
        }
    )

    if not compact.startswith(RECOVERY_CODE_PREFIX):
        raise ValueError("invalid recovery code")

    encoded = compact[len(RECOVERY_CODE_PREFIX) :]

    if len(encoded) != RECOVERY_ENCODED_LENGTH:
        raise ValueError("invalid recovery code")

    if any(character not in _BASE32_ALPHABET for character in encoded):
        raise ValueError("invalid recovery code")

    try:
        payload = base64.b32decode(
            encoded,
            casefold=False,
        )
    except (
        binascii.Error,
        ValueError,
    ):
        raise ValueError("invalid recovery code") from None

    if len(payload) != RECOVERY_PAYLOAD_LENGTH:
        raise ValueError("invalid recovery code")

    return RecoveryCredential(
        recovery_id=payload[:RECOVERY_ID_LENGTH],
        secret=payload[RECOVERY_ID_LENGTH:],
    )


def derive_recovery_key_encryption_key(
    password_key: bytes,
    credential: RecoveryCredential,
    *,
    vault_id: bytes,
) -> bytes:
    """Combine the password key and recovery secret with HKDF-SHA256."""
    _require_bytes_length(
        "password_key",
        password_key,
        PASSWORD_KEY_LENGTH,
    )

    if not isinstance(
        credential,
        RecoveryCredential,
    ):
        raise TypeError("credential must be RecoveryCredential")

    if not isinstance(
        vault_id,
        bytes,
    ):
        raise TypeError("vault_id must be bytes")

    if not vault_id:
        raise ValueError("vault_id must not be empty")

    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_ENCRYPTION_KEY_LENGTH,
        salt=credential.secret,
        info=(RECOVERY_KEY_CONTEXT + vault_id + credential.recovery_id),
    ).derive(password_key)


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
