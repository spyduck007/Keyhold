"""Versioned encrypted manifest for vault contents."""

from __future__ import annotations

from dataclasses import dataclass

from usb_vault.core.errors import VaultFormatError
from usb_vault.core.serialization import (
    canonical_json_bytes,
    parse_json_object,
    require_exact_keys,
    require_integer,
    require_list,
    require_string,
)
from usb_vault.core.storage.format import VAULT_ID_LENGTH

MANIFEST_MAGIC = "USBVAULTMANIFEST"
MANIFEST_VERSION = 1
MANIFEST_AAD_PREFIX = b"USBVAULT|manifest|v1|"
INVALID_MANIFEST_MESSAGE = "Invalid vault manifest."

_MANIFEST_FIELDS = {
    "magic",
    "version",
    "entries",
}


@dataclass(frozen=True, slots=True)
class VaultManifest:
    """The initial empty manifest used before file-entry support is added."""

    version: int = MANIFEST_VERSION

    def __post_init__(self) -> None:
        if self.version != MANIFEST_VERSION:
            raise ValueError(f"unsupported manifest version: {self.version}")

    @property
    def entry_count(self) -> int:
        """Return the number of stored entries."""
        return 0

    def to_bytes(self) -> bytes:
        """Serialize the empty manifest deterministically."""
        payload: dict[str, object] = {
            "magic": MANIFEST_MAGIC,
            "version": self.version,
            "entries": [],
        }

        return canonical_json_bytes(payload)

    @classmethod
    def from_bytes(cls, data: bytes) -> VaultManifest:
        """Parse the current empty-manifest format."""
        try:
            payload = parse_json_object(data)

            require_exact_keys(
                payload,
                _MANIFEST_FIELDS,
                object_name="vault manifest",
            )

            magic = require_string(
                payload["magic"],
                field_name="magic",
            )
            version = require_integer(
                payload["version"],
                field_name="version",
            )
            entries = require_list(
                payload["entries"],
                field_name="entries",
            )

            if magic != MANIFEST_MAGIC:
                raise ValueError("invalid manifest magic")

            if version != MANIFEST_VERSION:
                raise ValueError("unsupported manifest version")

            if entries:
                raise ValueError("manifest entries are not supported yet")

            return cls(version=version)
        except (TypeError, ValueError):
            raise VaultFormatError(INVALID_MANIFEST_MESSAGE) from None


def create_empty_manifest() -> VaultManifest:
    """Create a new empty vault manifest."""
    return VaultManifest()


def manifest_associated_data(vault_id: bytes) -> bytes:
    """Bind encrypted manifest data to one specific vault identifier."""
    if not isinstance(vault_id, bytes):
        raise TypeError("vault_id must be bytes")

    if len(vault_id) != VAULT_ID_LENGTH:
        raise ValueError(f"vault_id must be exactly {VAULT_ID_LENGTH} bytes")

    return MANIFEST_AAD_PREFIX + vault_id
