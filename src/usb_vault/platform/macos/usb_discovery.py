"""Discover registered USB Vault keyfiles on mounted macOS volumes."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.core.storage.reader import (
    read_usb_keyfile,
    read_vault_container,
)

DEFAULT_VOLUMES_ROOT = Path("/Volumes")
KEYFILE_SUFFIX = ".authkey"


class UsbKeyLocator(Protocol):
    """Locate a mounted USB key registered to one vault."""

    def find_matching_keyfile(
        self,
        vault_path: Path,
    ) -> Path | None:
        """Return a matching mounted keyfile, or None."""


@dataclass(frozen=True, slots=True)
class MacOsUsbKeyLocator:
    """Scan root-level keyfiles on mounted macOS volumes."""

    volumes_root: Path = DEFAULT_VOLUMES_ROOT

    def find_matching_keyfile(
        self,
        vault_path: Path,
    ) -> Path | None:
        """Find the first mounted keyfile registered to the vault."""
        container = read_vault_container(vault_path)
        registered_key_ids = tuple(slot.key_id for slot in (container.header.key_slots))

        for candidate_path in self._candidate_keyfile_paths():
            try:
                keyfile = read_usb_keyfile(candidate_path)
            except (
                VaultError,
                OSError,
                ValueError,
            ):
                continue

            if any(
                hmac.compare_digest(
                    keyfile.key_id,
                    registered_key_id,
                )
                for registered_key_id in registered_key_ids
            ):
                return candidate_path

        return None

    def _candidate_keyfile_paths(
        self,
    ) -> tuple[Path, ...]:
        """Return deterministic root-level .authkey candidates."""
        volume_paths = self._mounted_volume_paths()
        candidates: list[Path] = []

        for volume_path in volume_paths:
            try:
                with os.scandir(volume_path) as entries:
                    for entry in entries:
                        if not entry.name.endswith(KEYFILE_SUFFIX):
                            continue

                        try:
                            is_regular_file = entry.is_file(follow_symlinks=False)
                        except OSError:
                            continue

                        if not is_regular_file:
                            continue

                        candidates.append(Path(entry.path))
            except OSError:
                continue

        return tuple(
            sorted(
                candidates,
                key=lambda path: (
                    path.parent.name.casefold(),
                    path.name.casefold(),
                    str(path),
                ),
            )
        )

    def _mounted_volume_paths(
        self,
    ) -> tuple[Path, ...]:
        """Return non-symlink directories beneath the volumes root."""
        try:
            with os.scandir(self.volumes_root) as entries:
                volume_paths: list[Path] = []

                for entry in entries:
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        continue

                    if is_directory:
                        volume_paths.append(Path(entry.path))
        except OSError:
            return ()

        return tuple(
            sorted(
                volume_paths,
                key=lambda path: (
                    path.name.casefold(),
                    str(path),
                ),
            )
        )
