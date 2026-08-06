"""Versioned serialization for the USB possession-factor keyfile."""

from __future__ import annotations

from dataclasses import dataclass

from usb_vault.core.crypto.random import (
    USB_SECRET_LENGTH,
    generate_usb_secret,
    secure_random_bytes,
)
from usb_vault.core.errors import VaultFormatError
from usb_vault.core.serialization import (
    canonical_json_bytes,
    decode_base64,
    encode_base64,
    parse_json_object,
    require_exact_keys,
    require_integer,
    require_string,
)

KEYFILE_MAGIC = "USBVAULTKEY"
KEYFILE_VERSION = 1
KEY_ID_LENGTH = 16
INVALID_KEYFILE_MESSAGE = "Invalid USB keyfile."

_KEYFILE_FIELDS = {
    "magic",
    "version",
    "key_id",
    "secret",
}


@dataclass(frozen=True, slots=True)
class UsbKeyfile:
    """The non-secret identifier and secret stored on an authentication USB."""

    key_id: bytes
    secret: bytes
    version: int = KEYFILE_VERSION

    def __post_init__(self) -> None:
        _require_bytes_length(
            "key_id",
            self.key_id,
            KEY_ID_LENGTH,
        )
        _require_bytes_length(
            "secret",
            self.secret,
            USB_SECRET_LENGTH,
        )

        if self.version != KEYFILE_VERSION:
            raise ValueError(f"unsupported keyfile version: {self.version}")

    def to_bytes(self) -> bytes:
        """Serialize the keyfile into deterministic JSON bytes."""
        payload: dict[str, object] = {
            "magic": KEYFILE_MAGIC,
            "version": self.version,
            "key_id": encode_base64(self.key_id),
            "secret": encode_base64(self.secret),
        }

        return canonical_json_bytes(payload)

    @classmethod
    def from_bytes(cls, data: bytes) -> UsbKeyfile:
        """Parse and validate a serialized USB keyfile."""
        try:
            payload = parse_json_object(data)

            require_exact_keys(
                payload,
                _KEYFILE_FIELDS,
                object_name="USB keyfile",
            )

            magic = require_string(
                payload["magic"],
                field_name="magic",
            )
            version = require_integer(
                payload["version"],
                field_name="version",
            )

            if magic != KEYFILE_MAGIC:
                raise ValueError("invalid keyfile magic")

            if version != KEYFILE_VERSION:
                raise ValueError("unsupported keyfile version")

            return cls(
                key_id=decode_base64(
                    payload["key_id"],
                    field_name="key_id",
                ),
                secret=decode_base64(
                    payload["secret"],
                    field_name="secret",
                ),
                version=version,
            )
        except (TypeError, ValueError):
            raise VaultFormatError(INVALID_KEYFILE_MESSAGE) from None


def create_usb_keyfile() -> UsbKeyfile:
    """Create a new keyfile using independently random values."""
    return UsbKeyfile(
        key_id=secure_random_bytes(KEY_ID_LENGTH),
        secret=generate_usb_secret(),
    )


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
