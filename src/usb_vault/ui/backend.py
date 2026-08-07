"""Testable bridge between the desktop UI and vault core."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
    add_file as core_add_file,
    create_folder as core_create_folder,
    delete_file as core_delete_file,
    delete_folder as core_delete_folder,
    extract_file as core_extract_file,
    list_files as core_list_files,
)


@dataclass(slots=True)
class UnlockedVault:
    """Paths and a mutable password buffer for one UI session."""

    vault_path: Path
    keyfile_path: Path
    _password: bytearray = field(repr=False)
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
        keyfile_path: str | Path,
        password: str,
    ) -> UnlockedVault:
        """Create UI session credentials from validated input."""
        if not isinstance(password, str):
            raise TypeError("password must be a string")

        password_bytes = password.encode("utf-8")

        if not password_bytes:
            raise ValueError("password must not be empty")

        return cls(
            vault_path=Path(vault_path),
            keyfile_path=Path(keyfile_path),
            _password=bytearray(password_bytes),
        )

    @property
    def is_closed(self) -> bool:
        """Return whether the mutable password buffer was cleared."""
        return self._closed

    def password_bytes(self) -> bytes:
        """Return a short-lived password copy for a core operation."""
        if self._closed:
            raise RuntimeError("vault UI session is locked")

        return bytes(self._password)

    def close(self) -> None:
        """Overwrite the mutable password buffer."""
        if self._closed:
            return

        for index in range(len(self._password)):
            self._password[index] = 0

        self._closed = True


class VaultBackend(Protocol):
    """Operations required by the desktop window."""

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        """Verify credentials and return the vault entries."""

    def list_entries(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        """Return current entry metadata."""

    def add_file(
        self,
        vault: UnlockedVault,
        source_path: Path,
        stored_name: str | None = None,
    ) -> VaultEntrySummary:
        """Add one file."""

    def extract_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        """Extract one file."""

    def delete_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
    ) -> VaultEntrySummary:
        """Delete one file."""

    def create_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> VaultEntrySummary:
        """Create one empty folder."""

    def delete_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        """Delete one folder and everything nested inside it."""


class CoreVaultBackend:
    """Production UI backend using the existing vault core."""

    def unlock(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        """Verify credentials by listing encrypted metadata."""
        return core_list_files(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
        )

    def list_entries(
        self,
        vault: UnlockedVault,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        """Return current entry metadata."""
        return core_list_files(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
        )

    def add_file(
        self,
        vault: UnlockedVault,
        source_path: Path,
        stored_name: str | None = None,
    ) -> VaultEntrySummary:
        """Encrypt one file into the vault."""
        return core_add_file(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            source_path=source_path,
            stored_name=stored_name,
        )

    def extract_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        """Decrypt one file to a chosen output path."""
        return core_extract_file(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            stored_name=stored_name,
            destination_path=(destination_path),
            overwrite=overwrite,
        )

    def delete_file(
        self,
        vault: UnlockedVault,
        stored_name: str,
    ) -> VaultEntrySummary:
        """Delete one encrypted file."""
        return core_delete_file(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            stored_name=stored_name,
        )

    def create_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> VaultEntrySummary:
        """Create one empty folder using a hidden marker entry."""
        return core_create_folder(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            folder_path=folder_path,
        )

    def delete_folder(
        self,
        vault: UnlockedVault,
        folder_path: str,
    ) -> tuple[
        VaultEntrySummary,
        ...,
    ]:
        """Delete one folder and everything nested inside it."""
        return core_delete_folder(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            folder_path=folder_path,
        )
