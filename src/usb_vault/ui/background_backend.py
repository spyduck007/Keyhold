"""Background-safe bridge for long-running vault file operations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from usb_vault.core.errors import (
    VaultError,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
    add_file as core_add_file,
    delete_file as core_delete_file,
    extract_file as core_extract_file,
    list_files as core_list_files,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)

EXPECTED_OPERATION_ERRORS = (
    VaultError,
    OSError,
    ValueError,
    RuntimeError,
)


@dataclass(slots=True)
class BackgroundVaultCredentials:
    """Independent credentials whose password buffer can be cleared."""

    vault_path: Path
    keyfile_path: Path
    _password: bytearray = field(repr=False)
    _closed: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    @classmethod
    def from_unlocked(
        cls,
        vault: UnlockedVault,
    ) -> BackgroundVaultCredentials:
        """Copy credentials for one background operation."""
        if not isinstance(
            vault,
            UnlockedVault,
        ):
            raise TypeError("vault must be UnlockedVault")

        return cls(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            _password=bytearray(vault.password_bytes()),
        )

    @property
    def is_closed(self) -> bool:
        """Return whether the password buffer was cleared."""
        return self._closed

    def password_bytes(self) -> bytes:
        """Return a short-lived immutable password copy."""
        if self._closed:
            raise RuntimeError("background credentials are closed")

        return bytes(self._password)

    def close(self) -> None:
        """Overwrite the mutable password buffer."""
        if self._closed:
            return

        for index in range(len(self._password)):
            self._password[index] = 0

        self._closed = True


@dataclass(frozen=True, slots=True)
class FileOperationFailure:
    """One source file that could not be added."""

    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class AddFilesResult:
    """Results from one sequential background import batch."""

    added: tuple[
        VaultEntrySummary,
        ...,
    ]
    failures: tuple[
        FileOperationFailure,
        ...,
    ]
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]


@dataclass(frozen=True, slots=True)
class DeleteFileResult:
    """Deleted entry and the refreshed vault listing."""

    deleted: VaultEntrySummary
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]


class BackgroundVaultBackend(Protocol):
    """Long-running operations used by the asynchronous window."""

    def add_files(
        self,
        credentials: BackgroundVaultCredentials,
        source_paths: Sequence[Path],
    ) -> AddFilesResult:
        """Add files sequentially and refresh the manifest."""

    def extract_file(
        self,
        credentials: BackgroundVaultCredentials,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        """Export one encrypted entry."""

    def delete_file(
        self,
        credentials: BackgroundVaultCredentials,
        stored_name: str,
    ) -> DeleteFileResult:
        """Delete one entry and refresh the manifest."""


class CoreBackgroundVaultBackend:
    """Production background backend using the streaming core."""

    def add_files(
        self,
        credentials: BackgroundVaultCredentials,
        source_paths: Sequence[Path],
    ) -> AddFilesResult:
        """Add each source independently and continue after failures."""
        added: list[VaultEntrySummary] = []
        failures: list[FileOperationFailure] = []

        for source_path in source_paths:
            try:
                result = core_add_file(
                    vault_path=(credentials.vault_path),
                    keyfile_path=(credentials.keyfile_path),
                    password=(credentials.password_bytes()),
                    source_path=(source_path),
                )
            except EXPECTED_OPERATION_ERRORS as error:
                message = str(error).strip()

                if not message:
                    message = "Unable to add file."

                failures.append(
                    FileOperationFailure(
                        path=source_path,
                        message=message,
                    )
                )
            else:
                added.append(result)

        entries = core_list_files(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
        )

        return AddFilesResult(
            added=tuple(added),
            failures=tuple(failures),
            entries=entries,
        )

    def extract_file(
        self,
        credentials: BackgroundVaultCredentials,
        stored_name: str,
        destination_path: Path,
        *,
        overwrite: bool = False,
    ) -> VaultEntrySummary:
        """Export one encrypted entry."""
        return core_extract_file(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
            stored_name=stored_name,
            destination_path=(destination_path),
            overwrite=overwrite,
        )

    def delete_file(
        self,
        credentials: BackgroundVaultCredentials,
        stored_name: str,
    ) -> DeleteFileResult:
        """Delete one entry and return refreshed metadata."""
        deleted = core_delete_file(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
            stored_name=stored_name,
        )
        entries = core_list_files(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
        )

        return DeleteFileResult(
            deleted=deleted,
            entries=entries,
        )
