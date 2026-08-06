"""In-memory state for one unlocked vault session."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from usb_vault.core.crypto.random import MASTER_KEY_LENGTH
from usb_vault.core.storage.format import VaultHeader
from usb_vault.core.vault.manifest import VaultManifest


@dataclass(slots=True)
class VaultSession:
    """An unlocked vault whose mutable master-key buffer can be cleared."""

    vault_path: Path
    header: VaultHeader
    manifest: VaultManifest
    _master_key: bytearray = field(repr=False)
    _closed: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    @classmethod
    def create(
        cls,
        *,
        vault_path: str | Path,
        header: VaultHeader,
        manifest: VaultManifest,
        master_key: bytes,
    ) -> VaultSession:
        """Create a session from a validated master key."""
        if not isinstance(master_key, bytes):
            raise TypeError("master_key must be bytes")

        if len(master_key) != MASTER_KEY_LENGTH:
            raise ValueError(f"master_key must be exactly {MASTER_KEY_LENGTH} bytes")

        return cls(
            vault_path=Path(vault_path),
            header=header,
            manifest=manifest,
            _master_key=bytearray(master_key),
        )

    @property
    def is_closed(self) -> bool:
        """Return whether sensitive session state has been cleared."""
        return self._closed

    @property
    def entry_count(self) -> int:
        """Return the number of entries in the decrypted manifest."""
        self._require_open()
        return self.manifest.entry_count

    def close(self) -> None:
        """Overwrite the session's mutable master-key buffer."""
        if self._closed:
            return

        for index in range(len(self._master_key)):
            self._master_key[index] = 0

        self._closed = True

    def __enter__(self) -> VaultSession:
        self._require_open()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("vault session is closed")
