"""Versioned encrypted manifest for vault contents."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from usb_vault.core.crypto.random import secure_random_bytes
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    VaultFormatError,
)
from usb_vault.core.serialization import (
    canonical_json_bytes,
    decode_base64,
    encode_base64,
    parse_json_object,
    require_exact_keys,
    require_integer,
    require_list,
    require_object,
    require_string,
)
from usb_vault.core.storage.format import VAULT_ID_LENGTH
from usb_vault.core.vault.blob import (
    BLOB_ID_LENGTH,
)
from usb_vault.core.vault.chunk_stream import (
    MAX_PLAINTEXT_LENGTH,
)

MANIFEST_MAGIC = "USBVAULTMANIFEST"
LEGACY_MANIFEST_VERSION = 1
MANIFEST_VERSION = 2
MANIFEST_AAD_PREFIX = b"USBVAULT|manifest|v1|"
INVALID_MANIFEST_MESSAGE = "Invalid vault manifest."

ENTRY_ID_LENGTH = 16
MAX_ENTRY_NAME_BYTES = 255
MAX_ENTRY_PATH_BYTES = 1_024
MAX_PATH_SEGMENTS = 32
FOLDER_MARKER_NAME = ".vaultkeep"

_MANIFEST_FIELDS = {
    "magic",
    "version",
    "entries",
}

_ENTRY_FIELDS = {
    "entry_id",
    "blob_id",
    "name",
    "size",
}


@dataclass(frozen=True, slots=True)
class VaultEntry:
    """Metadata for one root-level file stored in the vault."""

    entry_id: bytes
    blob_id: bytes
    name: str
    size: int

    def __post_init__(self) -> None:
        _require_bytes_length(
            "entry_id",
            self.entry_id,
            ENTRY_ID_LENGTH,
        )
        _require_bytes_length(
            "blob_id",
            self.blob_id,
            BLOB_ID_LENGTH,
        )

        normalized_name = normalize_entry_name(self.name)
        object.__setattr__(
            self,
            "name",
            normalized_name,
        )

        if type(self.size) is not int:
            raise TypeError("size must be an integer")

        if self.size < 0:
            raise ValueError("size must not be negative")

        if self.size > MAX_PLAINTEXT_LENGTH:
            raise ValueError("size exceeds the supported file limit")

    def to_object(self) -> dict[str, object]:
        """Return this entry's JSON-compatible representation."""
        return {
            "entry_id": encode_base64(self.entry_id),
            "blob_id": encode_base64(self.blob_id),
            "name": self.name,
            "size": self.size,
        }

    @classmethod
    def from_object(
        cls,
        value: object,
    ) -> VaultEntry:
        """Parse one strict manifest entry."""
        payload = require_object(
            value,
            field_name="manifest entry",
        )

        require_exact_keys(
            payload,
            _ENTRY_FIELDS,
            object_name="manifest entry",
        )

        return cls(
            entry_id=decode_base64(
                payload["entry_id"],
                field_name="entry_id",
            ),
            blob_id=decode_base64(
                payload["blob_id"],
                field_name="blob_id",
            ),
            name=require_string(
                payload["name"],
                field_name="name",
            ),
            size=require_integer(
                payload["size"],
                field_name="size",
            ),
        )


@dataclass(frozen=True, slots=True)
class VaultManifest:
    """Encrypted metadata describing root-level vault files."""

    entries: tuple[VaultEntry, ...] = ()
    version: int = MANIFEST_VERSION

    def __post_init__(self) -> None:
        if self.version != MANIFEST_VERSION:
            raise ValueError(f"unsupported manifest version: {self.version}")

        if not isinstance(
            self.entries,
            tuple,
        ):
            raise TypeError("entries must be a tuple")

        if not all(isinstance(entry, VaultEntry) for entry in self.entries):
            raise TypeError("every manifest entry must be VaultEntry")

        _require_unique_entries(self.entries)

    @property
    def entry_count(self) -> int:
        """Return the number of stored entries."""
        return len(self.entries)

    def to_bytes(self) -> bytes:
        """Serialize the manifest deterministically."""
        ordered_entries = sorted(
            self.entries,
            key=lambda entry: (
                entry.name.casefold(),
                entry.name,
                entry.entry_id,
            ),
        )

        payload: dict[str, object] = {
            "magic": MANIFEST_MAGIC,
            "version": self.version,
            "entries": [entry.to_object() for entry in ordered_entries],
        }

        return canonical_json_bytes(payload)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
    ) -> VaultManifest:
        """Parse version 2 or migrate an empty version 1 manifest."""
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
            raw_entries = require_list(
                payload["entries"],
                field_name="entries",
            )

            if magic != MANIFEST_MAGIC:
                raise ValueError("invalid manifest magic")

            if version == LEGACY_MANIFEST_VERSION:
                if raw_entries:
                    raise ValueError("legacy manifests must be empty")

                return cls()

            if version != MANIFEST_VERSION:
                raise ValueError("unsupported manifest version")

            return cls(
                entries=tuple(VaultEntry.from_object(entry) for entry in raw_entries),
            )
        except (TypeError, ValueError):
            raise VaultFormatError(INVALID_MANIFEST_MESSAGE) from None

    def find_by_name(
        self,
        name: str,
    ) -> VaultEntry | None:
        """Find an entry using a case-insensitive name policy."""
        normalized_name = normalize_entry_name(name)
        comparison_name = normalized_name.casefold()

        for entry in self.entries:
            if entry.name.casefold() == comparison_name:
                return entry

        return None

    def add_entry(
        self,
        entry: VaultEntry,
    ) -> VaultManifest:
        """Return a manifest containing a new entry."""
        if not isinstance(
            entry,
            VaultEntry,
        ):
            raise TypeError("entry must be VaultEntry")

        if self.find_by_name(entry.name) is not None:
            raise EntryExistsError(f"Vault entry already exists: {entry.name}")

        return VaultManifest(
            entries=(
                *self.entries,
                entry,
            )
        )

    def remove_entry(
        self,
        name: str,
    ) -> tuple[VaultManifest, VaultEntry]:
        """Return a new manifest and the removed entry."""
        existing = self.find_by_name(name)

        if existing is None:
            normalized_name = normalize_entry_name(name)
            raise EntryNotFoundError(f"Vault entry not found: {normalized_name}")

        remaining = tuple(entry for entry in self.entries if (entry.entry_id != existing.entry_id))

        return (
            VaultManifest(entries=remaining),
            existing,
        )


def create_empty_manifest() -> VaultManifest:
    """Create a new empty vault manifest."""
    return VaultManifest()


def create_vault_entry(
    *,
    name: str,
    size: int,
    blob_id: bytes,
    entry_id: bytes | None = None,
) -> VaultEntry:
    """Create file metadata with a stable random identifier."""
    selected_entry_id = entry_id if entry_id is not None else secure_random_bytes(ENTRY_ID_LENGTH)

    return VaultEntry(
        entry_id=selected_entry_id,
        blob_id=blob_id,
        name=name,
        size=size,
    )


def normalize_entry_name(
    name: str,
) -> str:
    """Normalize and validate one filename or '/'-delimited folder path."""
    if not isinstance(name, str):
        raise TypeError("name must be a string")

    normalized = unicodedata.normalize(
        "NFC",
        name,
    )

    if not normalized or normalized.isspace():
        raise ValueError("name must not be empty")

    if "\x00" in normalized or "\\" in normalized:
        raise ValueError("name contains unsupported characters")

    if normalized.startswith("/") or normalized.endswith("/"):
        raise ValueError("name must not start or end with '/'")

    if len(normalized.encode("utf-8")) > MAX_ENTRY_PATH_BYTES:
        raise ValueError("name is too long")

    segments = normalized.split("/")

    if len(segments) > MAX_PATH_SEGMENTS:
        raise ValueError("name has too many folder levels")

    for segment in segments:
        _require_safe_path_segment(segment)

    return normalized


def _require_safe_path_segment(segment: str) -> None:
    if not segment or segment.isspace():
        raise ValueError("name must not contain empty path segments")

    if segment in {".", ".."}:
        raise ValueError("name is not allowed")

    if len(segment.encode("utf-8")) > MAX_ENTRY_NAME_BYTES:
        raise ValueError("a path segment is too long")


def folder_marker_name(folder_path: str) -> str:
    """Return the hidden marker entry name that keeps a folder listed when empty."""
    normalized_folder = normalize_entry_name(folder_path)
    return normalize_entry_name(f"{normalized_folder}/{FOLDER_MARKER_NAME}")


def manifest_associated_data(
    vault_id: bytes,
) -> bytes:
    """Bind encrypted metadata to one vault identifier."""
    _require_bytes_length(
        "vault_id",
        vault_id,
        VAULT_ID_LENGTH,
    )

    return MANIFEST_AAD_PREFIX + vault_id


def _require_unique_entries(
    entries: tuple[VaultEntry, ...],
) -> None:
    entry_ids = [entry.entry_id for entry in entries]
    blob_ids = [entry.blob_id for entry in entries]
    comparison_names = [entry.name.casefold() for entry in entries]

    if len(entry_ids) != len(set(entry_ids)):
        raise ValueError("manifest entry identifiers must be unique")

    if len(blob_ids) != len(set(blob_ids)):
        raise ValueError("manifest blob identifiers must be unique")

    if len(comparison_names) != len(set(comparison_names)):
        raise ValueError("manifest entry names must be unique")


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
