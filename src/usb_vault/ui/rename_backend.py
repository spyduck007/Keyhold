"""Background bridge for encrypted entry renaming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
    list_files as core_list_files,
    move_folder as core_move_folder,
    rename_file as core_rename_file,
)
from usb_vault.ui.background_backend import (
    BackgroundVaultCredentials,
)


@dataclass(
    frozen=True,
    slots=True,
)
class RenameFileResult:
    """Renamed entry and refreshed display metadata."""

    renamed: VaultEntrySummary
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.renamed,
            VaultEntrySummary,
        ):
            raise TypeError("renamed must be VaultEntrySummary")

        if not isinstance(
            self.entries,
            tuple,
        ):
            raise TypeError("entries must be a tuple")


@dataclass(
    frozen=True,
    slots=True,
)
class MoveFolderResult:
    """Relocated folder entries and refreshed display metadata."""

    moved: tuple[
        VaultEntrySummary,
        ...,
    ]
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.moved,
            tuple,
        ):
            raise TypeError("moved must be a tuple")

        if not isinstance(
            self.entries,
            tuple,
        ):
            raise TypeError("entries must be a tuple")


class RenameVaultBackend(Protocol):
    """Background rename operation used by the desktop window."""

    def rename_file(
        self,
        credentials: (BackgroundVaultCredentials),
        stored_name: str,
        new_name: str,
    ) -> RenameFileResult:
        """Rename one entry and refresh the browser metadata."""

    def move_folder(
        self,
        credentials: (BackgroundVaultCredentials),
        folder_path: str,
        destination_folder_path: str,
    ) -> MoveFolderResult:
        """Move one folder and refresh the browser metadata."""


class CoreRenameVaultBackend:
    """Production rename backend using the vault core."""

    def rename_file(
        self,
        credentials: (BackgroundVaultCredentials),
        stored_name: str,
        new_name: str,
    ) -> RenameFileResult:
        """Rename one encrypted manifest entry."""
        renamed = core_rename_file(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
            stored_name=stored_name,
            new_name=new_name,
        )
        entries = core_list_files(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
        )

        return RenameFileResult(
            renamed=renamed,
            entries=entries,
        )

    def move_folder(
        self,
        credentials: (BackgroundVaultCredentials),
        folder_path: str,
        destination_folder_path: str,
    ) -> MoveFolderResult:
        """Move one folder and everything nested inside it."""
        moved = core_move_folder(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
            folder_path=folder_path,
            destination_folder_path=destination_folder_path,
        )
        entries = core_list_files(
            vault_path=(credentials.vault_path),
            keyfile_path=(credentials.keyfile_path),
            password=(credentials.password_bytes()),
        )

        return MoveFolderResult(
            moved=moved,
            entries=entries,
        )
