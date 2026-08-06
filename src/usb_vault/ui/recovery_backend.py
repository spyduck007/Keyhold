"""Testable bridge for restoring USB access from the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
    list_files as core_list_files,
)
from usb_vault.core.vault.recovery import (
    recover_usb_key as core_recover_usb_key,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)


@dataclass(slots=True)
class RecoveredVault:
    """A recovered vault ready to display in the desktop UI."""

    vault: UnlockedVault
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]
    recovery_code: str
    replaced_existing_keys: bool

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

        if type(self.replaced_existing_keys) is not bool:
            raise TypeError("replaced_existing_keys must be a boolean")


class VaultRecoveryBackend(Protocol):
    """Operations required by the desktop recovery workflow."""

    def recover_vault(
        self,
        *,
        vault_path: Path,
        new_keyfile_path: Path,
        password: str,
        recovery_code: str,
        replace_existing_keys: bool,
    ) -> RecoveredVault:
        """Restore USB access and return an opened UI session."""


class CoreVaultRecoveryBackend:
    """Production recovery backend using the vault core."""

    def recover_vault(
        self,
        *,
        vault_path: Path,
        new_keyfile_path: Path,
        password: str,
        recovery_code: str,
        replace_existing_keys: bool,
    ) -> RecoveredVault:
        """Create a replacement USB and rotate the recovery code."""
        vault = UnlockedVault.create(
            vault_path=vault_path,
            keyfile_path=new_keyfile_path,
            password=password,
        )

        try:
            result = core_recover_usb_key(
                vault_path=vault_path,
                password=(vault.password_bytes()),
                recovery_code=recovery_code,
                new_keyfile_path=(new_keyfile_path),
                replace_existing_keys=(replace_existing_keys),
            )
            entries = core_list_files(
                vault_path=vault_path,
                keyfile_path=(new_keyfile_path),
                password=(vault.password_bytes()),
            )
        except Exception:
            vault.close()
            raise

        return RecoveredVault(
            vault=vault,
            entries=entries,
            recovery_code=(result.recovery_code),
            replaced_existing_keys=(result.replaced_existing_keys),
        )
