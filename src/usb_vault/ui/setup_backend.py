"""Testable bridge for creating a vault from the desktop UI."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from usb_vault.core.vault.creator import (
    create_vault as core_create_vault,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
    list_files as core_list_files,
)
from usb_vault.core.vault.recovery import (
    create_recovery_code as core_create_recovery_code,
)
from usb_vault.ui.backend import UnlockedVault


@dataclass(slots=True)
class CreatedVault:
    """A newly created vault ready to display in the UI."""

    vault: UnlockedVault
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]
    recovery_code: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.vault,
            UnlockedVault,
        ):
            raise TypeError("vault must be UnlockedVault")

        if not isinstance(
            self.entries,
            tuple,
        ):
            raise TypeError("entries must be a tuple")

        if not isinstance(
            self.recovery_code,
            str,
        ):
            raise TypeError("recovery_code must be a string")

        if not self.recovery_code:
            raise ValueError("recovery_code must not be empty")


class VaultSetupBackend(Protocol):
    """Operations required by the new-vault wizard."""

    def create_vault(
        self,
        *,
        vault_path: Path,
        keyfile_path: Path,
        password: str,
    ) -> CreatedVault:
        """Create, configure recovery, and open a vault."""


class CoreVaultSetupBackend:
    """Production setup backend using the existing vault core."""

    def create_vault(
        self,
        *,
        vault_path: Path,
        keyfile_path: Path,
        password: str,
    ) -> CreatedVault:
        """Create a vault and its initial recovery code."""
        session = UnlockedVault.create(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=password,
        )
        vault_created = False

        try:
            core_create_vault(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                password=(session.password_bytes()),
            )
            vault_created = True

            recovery = core_create_recovery_code(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                password=(session.password_bytes()),
            )
            entries = core_list_files(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                password=(session.password_bytes()),
            )

            return CreatedVault(
                vault=session,
                entries=entries,
                recovery_code=(recovery.recovery_code),
            )
        except Exception:
            session.close()

            if vault_created:
                with suppress(FileNotFoundError):
                    vault_path.unlink()

                with suppress(FileNotFoundError):
                    keyfile_path.unlink()

            raise
