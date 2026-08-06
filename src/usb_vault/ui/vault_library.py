"""Persistent, non-secret registry of known encrypted vaults."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from usb_vault.core.errors import (
    VaultFormatError,
)
from usb_vault.core.storage.atomic_save import (
    atomic_write_bytes,
)
from usb_vault.core.storage.format import (
    VAULT_ID_LENGTH,
)
from usb_vault.core.storage.reader import (
    read_bytes_limited,
    read_vault_container,
)

LIBRARY_MAGIC = "USBVAULT-LIBRARY"
LIBRARY_VERSION = 1
MAX_LIBRARY_SIZE = 1_048_576
MAX_LIBRARY_ENTRIES = 1_000
MAX_DISPLAY_NAME_LENGTH = 120

LIBRARY_PATH_ENVIRONMENT_VARIABLE = "USB_VAULT_LIBRARY_PATH"

_LIBRARY_FIELDS = {
    "magic",
    "version",
    "vaults",
}

_ENTRY_FIELDS = {
    "vault_id",
    "display_name",
    "vault_path",
    "last_opened_at",
}

Clock = Callable[[], datetime]


class VaultLibraryError(RuntimeError):
    """Base class for persistent vault-library failures."""


class VaultLibraryFormatError(VaultLibraryError):
    """Raised when the stored vault library is malformed."""


class VaultIdentityReader(Protocol):
    """Read the public identity from an encrypted vault."""

    def read_vault_id(
        self,
        vault_path: Path,
    ) -> bytes:
        """Return the public vault identifier."""


class CoreVaultIdentityReader:
    """Production vault identity reader."""

    def read_vault_id(
        self,
        vault_path: Path,
    ) -> bytes:
        """Read the public identifier from a vault container."""
        return read_vault_container(vault_path).header.vault_id


@dataclass(frozen=True, slots=True)
class VaultLibraryEntry:
    """One non-secret known-vault record."""

    vault_id: bytes
    display_name: str
    vault_path: Path
    last_opened_at: datetime

    def __post_init__(self) -> None:
        _require_vault_id(self.vault_id)

        normalized_name = _normalize_display_name(self.display_name)

        if normalized_name != self.display_name:
            raise ValueError("display_name must already be normalized")

        if not isinstance(
            self.vault_path,
            Path,
        ):
            raise TypeError("vault_path must be Path")

        if not self.vault_path.is_absolute():
            raise ValueError("vault_path must be absolute")

        _require_aware_datetime(self.last_opened_at)

    @property
    def vault_id_hex(self) -> str:
        """Return the public vault identifier as hexadecimal."""
        return self.vault_id.hex()

    @property
    def is_available(self) -> bool:
        """Return whether the path currently names a regular file."""
        try:
            file_status = self.vault_path.stat(follow_symlinks=False)
        except OSError:
            return False

        return stat.S_ISREG(file_status.st_mode)

    def to_object(
        self,
    ) -> dict[str, object]:
        """Return the persistent JSON representation."""
        return {
            "vault_id": self.vault_id_hex,
            "display_name": (self.display_name),
            "vault_path": str(self.vault_path),
            "last_opened_at": (_format_timestamp(self.last_opened_at)),
        }

    @classmethod
    def from_object(
        cls,
        value: object,
    ) -> VaultLibraryEntry:
        """Parse one persistent library record."""
        payload = _require_object(
            value,
            field_name="vault entry",
        )
        _require_exact_keys(
            payload,
            _ENTRY_FIELDS,
            object_name="vault entry",
        )

        vault_id_hex = _require_string(
            payload["vault_id"],
            field_name="vault_id",
        )
        display_name = _require_string(
            payload["display_name"],
            field_name="display_name",
        )
        vault_path = _require_string(
            payload["vault_path"],
            field_name="vault_path",
        )
        last_opened_at = _require_string(
            payload["last_opened_at"],
            field_name="last_opened_at",
        )

        try:
            vault_id = bytes.fromhex(vault_id_hex)
        except ValueError as error:
            raise VaultLibraryFormatError("Invalid vault library.") from error

        return cls(
            vault_id=vault_id,
            display_name=display_name,
            vault_path=Path(vault_path),
            last_opened_at=(_parse_timestamp(last_opened_at)),
        )


class VaultLibraryStore:
    """Load and atomically update the local vault registry."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        identity_reader: (VaultIdentityReader | None) = None,
        clock: Clock | None = None,
    ) -> None:
        selected_path = (
            default_vault_library_path() if path is None else _normalize_path(Path(path))
        )

        self._path = selected_path
        self._identity_reader = (
            identity_reader if identity_reader is not None else CoreVaultIdentityReader()
        )
        self._clock = clock if clock is not None else _utc_now

    @property
    def path(self) -> Path:
        """Return the registry file location."""
        return self._path

    def list_entries(
        self,
    ) -> tuple[
        VaultLibraryEntry,
        ...,
    ]:
        """Return known vaults, most recently opened first."""
        entries = list(self._load_entries())

        entries.sort(
            key=lambda entry: (
                entry.display_name.casefold(),
                entry.display_name,
                str(entry.vault_path),
            )
        )
        entries.sort(
            key=lambda entry: entry.last_opened_at,
            reverse=True,
        )

        return tuple(entries)

    def find_vault(
        self,
        vault_id: bytes,
    ) -> VaultLibraryEntry | None:
        """Find one entry by its public vault identifier."""
        _require_vault_id(vault_id)

        for entry in self._load_entries():
            if entry.vault_id == vault_id:
                return entry

        return None

    def register_vault(
        self,
        vault_path: str | Path,
        *,
        display_name: str | None = None,
    ) -> VaultLibraryEntry:
        """Register or update a successfully opened vault."""
        normalized_path = _normalize_path(Path(vault_path))
        vault_id = self._identity_reader.read_vault_id(normalized_path)
        _require_vault_id(vault_id)

        opened_at = self._clock()
        _require_aware_datetime(opened_at)
        opened_at = opened_at.astimezone(UTC)

        entries = list(self._load_entries())
        existing = next(
            (entry for entry in entries if entry.vault_id == vault_id),
            None,
        )

        if display_name is not None:
            selected_name = _normalize_display_name(display_name)
        elif existing is not None:
            selected_name = existing.display_name
        else:
            selected_name = _default_display_name(normalized_path)

        updated_entry = VaultLibraryEntry(
            vault_id=vault_id,
            display_name=selected_name,
            vault_path=normalized_path,
            last_opened_at=opened_at,
        )

        # Deduplicate both by public identity and by path. A vault
        # opened from a new location updates the existing record.
        # A different vault replacing the same path replaces the
        # stale record for that path.
        remaining_entries = [
            entry
            for entry in entries
            if (entry.vault_id != vault_id and entry.vault_path != normalized_path)
        ]
        remaining_entries.append(updated_entry)

        self._save_entries(remaining_entries)

        return updated_entry

    def rename_vault(
        self,
        vault_id: bytes,
        display_name: str,
    ) -> VaultLibraryEntry:
        """Change only the local display name."""
        _require_vault_id(vault_id)
        normalized_name = _normalize_display_name(display_name)

        entries = list(self._load_entries())

        for index, entry in enumerate(entries):
            if entry.vault_id != vault_id:
                continue

            renamed_entry = VaultLibraryEntry(
                vault_id=(entry.vault_id),
                display_name=(normalized_name),
                vault_path=(entry.vault_path),
                last_opened_at=(entry.last_opened_at),
            )
            entries[index] = renamed_entry
            self._save_entries(entries)
            return renamed_entry

        raise VaultLibraryError("Vault is not registered.")

    def remove_vault(
        self,
        vault_id: bytes,
    ) -> bool:
        """Remove a registry entry without deleting the vault."""
        _require_vault_id(vault_id)

        entries = list(self._load_entries())
        remaining_entries = [entry for entry in entries if entry.vault_id != vault_id]

        if len(remaining_entries) == len(entries):
            return False

        self._save_entries(remaining_entries)
        return True

    def _load_entries(
        self,
    ) -> tuple[
        VaultLibraryEntry,
        ...,
    ]:
        try:
            data = read_bytes_limited(
                self._path,
                max_size=(MAX_LIBRARY_SIZE),
                error_message=("Invalid vault library."),
            )
        except FileNotFoundError:
            return ()
        except (
            OSError,
            VaultFormatError,
        ) as error:
            raise VaultLibraryFormatError("Invalid vault library.") from error

        try:
            decoded = data.decode("utf-8")
            parsed: object = json.loads(decoded)
            payload = _require_object(
                parsed,
                field_name=("vault library"),
            )
            _require_exact_keys(
                payload,
                _LIBRARY_FIELDS,
                object_name=("vault library"),
            )

            magic = _require_string(
                payload["magic"],
                field_name="magic",
            )
            version = _require_integer(
                payload["version"],
                field_name="version",
            )
            raw_entries = _require_list(
                payload["vaults"],
                field_name="vaults",
            )

            if magic != LIBRARY_MAGIC:
                raise ValueError("invalid library magic")

            if version != LIBRARY_VERSION:
                raise ValueError("unsupported library version")

            if len(raw_entries) > MAX_LIBRARY_ENTRIES:
                raise ValueError("too many vault entries")

            entries = tuple(VaultLibraryEntry.from_object(item) for item in raw_entries)

            vault_ids = [entry.vault_id for entry in entries]
            vault_paths = [entry.vault_path for entry in entries]

            if len(vault_ids) != len(set(vault_ids)):
                raise ValueError("duplicate vault identifiers")

            if len(vault_paths) != len(set(vault_paths)):
                raise ValueError("duplicate vault paths")

            return entries
        except VaultLibraryFormatError:
            raise
        except (
            json.JSONDecodeError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as error:
            raise VaultLibraryFormatError("Invalid vault library.") from error

    def _save_entries(
        self,
        entries: list[VaultLibraryEntry],
    ) -> None:
        if len(entries) > MAX_LIBRARY_ENTRIES:
            raise VaultLibraryError("Vault library contains too many entries.")

        ordered_entries = sorted(
            entries,
            key=lambda entry: entry.vault_id,
        )
        payload: dict[str, object] = {
            "magic": LIBRARY_MAGIC,
            "version": LIBRARY_VERSION,
            "vaults": [entry.to_object() for entry in ordered_entries],
        }
        serialized = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(
                    ",",
                    ":",
                ),
            ).encode("utf-8")
            + b"\n"
        )

        if len(serialized) > MAX_LIBRARY_SIZE:
            raise VaultLibraryError("Vault library is too large.")

        parent = self._path.parent
        parent.mkdir(
            mode=0o700,
            parents=True,
            exist_ok=True,
        )

        if not parent.is_dir():
            raise NotADirectoryError(f"Vault library parent is not a directory: {parent}")

        atomic_write_bytes(
            self._path,
            serialized,
            overwrite=True,
        )


def default_vault_library_path() -> Path:
    """Return the default per-user macOS registry path."""
    override = os.environ.get(LIBRARY_PATH_ENVIRONMENT_VARIABLE)

    if override is not None:
        if not override.strip():
            raise VaultLibraryError(f"{LIBRARY_PATH_ENVIRONMENT_VARIABLE} must not be empty.")

        return _normalize_path(Path(override))

    return _normalize_path(
        Path.home() / "Library" / "Application Support" / "USB Vault" / "vault-library.json"
    )


def _default_display_name(
    vault_path: Path,
) -> str:
    candidate = vault_path.stem.strip()

    if not candidate:
        candidate = "Vault"

    return _normalize_display_name(candidate)


def _normalize_display_name(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError("display_name must be a string")

    normalized = value.strip()

    if not normalized:
        raise ValueError("display_name must not be empty")

    if len(normalized) > MAX_DISPLAY_NAME_LENGTH:
        raise ValueError("display_name is too long")

    if any(
        character.isspace()
        and character
        not in {
            " ",
            "\t",
        }
        for character in normalized
    ):
        raise ValueError("display_name contains unsupported whitespace")

    if any(ord(character) < 32 and character != "\t" for character in normalized):
        raise ValueError("display_name contains control characters")

    return normalized


def _normalize_path(
    path: Path,
) -> Path:
    expanded = path.expanduser()

    return Path(os.path.abspath(os.fspath(expanded)))


def _require_vault_id(
    value: bytes,
) -> None:
    if not isinstance(
        value,
        bytes,
    ):
        raise TypeError("vault_id must be bytes")

    if len(value) != VAULT_ID_LENGTH:
        raise ValueError(f"vault_id must be exactly {VAULT_ID_LENGTH} bytes")


def _require_aware_datetime(
    value: datetime,
) -> None:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError("last_opened_at must be datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("last_opened_at must include a timezone")


def _format_timestamp(
    value: datetime,
) -> str:
    _require_aware_datetime(value)

    return (
        value.astimezone(UTC)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def _parse_timestamp(
    value: str,
) -> datetime:
    candidate = value

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise VaultLibraryFormatError("Invalid vault library.") from error

    _require_aware_datetime(parsed)

    return parsed.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_object(
    value: object,
    *,
    field_name: str,
) -> dict[str, object]:
    if not isinstance(
        value,
        dict,
    ):
        raise TypeError(f"{field_name} must be an object")

    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} keys must be strings")

    return cast(
        dict[str, object],
        value,
    )


def _require_list(
    value: object,
    *,
    field_name: str,
) -> list[object]:
    if not isinstance(
        value,
        list,
    ):
        raise TypeError(f"{field_name} must be a list")

    return cast(
        list[object],
        value,
    )


def _require_string(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(f"{field_name} must be a string")

    return value


def _require_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")

    return value


def _require_exact_keys(
    payload: dict[str, object],
    expected_keys: set[str],
    *,
    object_name: str,
) -> None:
    if set(payload) != expected_keys:
        raise ValueError(f"{object_name} contains unexpected fields")
