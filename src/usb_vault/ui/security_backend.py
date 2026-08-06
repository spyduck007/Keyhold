"""Testable bridge for desktop USB-key and password management."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.vault.key_management import (
    UsbKeySummary,
    add_usb_key,
    list_usb_keys,
    parse_key_id_hex,
    revoke_usb_key,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
    list_files,
)
from usb_vault.core.vault.password_management import (
    change_vault_password,
)
from usb_vault.ui.backend import (
    UnlockedVault,
)


@dataclass(frozen=True, slots=True)
class SecuritySnapshot:
    """Public security metadata for the open vault."""

    keys: tuple[
        UsbKeySummary,
        ...,
    ]
    recovery_configured: bool

    def __post_init__(self) -> None:
        if not isinstance(
            self.keys,
            tuple,
        ):
            raise TypeError("keys must be a tuple")

        if not self.keys:
            raise ValueError("keys must not be empty")

        if not all(
            isinstance(
                key,
                UsbKeySummary,
            )
            for key in self.keys
        ):
            raise TypeError("every key must be UsbKeySummary")

        if type(self.recovery_configured) is not bool:
            raise TypeError("recovery_configured must be a boolean")

    @property
    def additional_keyfile_count(
        self,
    ) -> int:
        """Return how many non-current keyfiles password rotation needs."""
        return max(
            0,
            len(self.keys) - 1,
        )


@dataclass(slots=True)
class PasswordUpdatedVault:
    """A newly authenticated UI session after password rotation."""

    vault: UnlockedVault
    entries: tuple[
        VaultEntrySummary,
        ...,
    ]
    key_count: int
    recovery_updated: bool

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

        if type(self.key_count) is not int:
            raise TypeError("key_count must be an integer")

        if self.key_count <= 0:
            raise ValueError("key_count must be greater than zero")

        if type(self.recovery_updated) is not bool:
            raise TypeError("recovery_updated must be a boolean")


class VaultSecurityBackend(Protocol):
    """Operations required by the desktop Security Center."""

    def snapshot(
        self,
        vault: UnlockedVault,
    ) -> SecuritySnapshot:
        """Return current public key and recovery metadata."""

    def add_key(
        self,
        vault: UnlockedVault,
        new_keyfile_path: Path,
    ) -> UsbKeySummary:
        """Create and register an independent USB key."""

    def revoke_key(
        self,
        vault: UnlockedVault,
        key_id_hex: str,
    ) -> UsbKeySummary:
        """Revoke one registered non-current USB key."""

    def change_password(
        self,
        vault: UnlockedVault,
        *,
        current_password: str,
        new_password: str,
        additional_keyfile_paths: Sequence[Path],
        recovery_code: str,
    ) -> PasswordUpdatedVault:
        """Rotate the password and return a new UI session."""


class CoreVaultSecurityBackend:
    """Production Security Center backend using the vault core."""

    def snapshot(
        self,
        vault: UnlockedVault,
    ) -> SecuritySnapshot:
        """Return current public key and recovery metadata."""
        keys = list_usb_keys(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
        )
        container = read_vault_container(vault.vault_path)

        return SecuritySnapshot(
            keys=keys,
            recovery_configured=bool(container.header.recovery_slots),
        )

    def add_key(
        self,
        vault: UnlockedVault,
        new_keyfile_path: Path,
    ) -> UsbKeySummary:
        """Create and register an independent USB key."""
        return add_usb_key(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            new_keyfile_path=(new_keyfile_path),
        )

    def revoke_key(
        self,
        vault: UnlockedVault,
        key_id_hex: str,
    ) -> UsbKeySummary:
        """Revoke one registered non-current USB key."""
        return revoke_usb_key(
            vault_path=vault.vault_path,
            keyfile_path=(vault.keyfile_path),
            password=(vault.password_bytes()),
            target_key_id=(parse_key_id_hex(key_id_hex)),
        )

    def change_password(
        self,
        vault: UnlockedVault,
        *,
        current_password: str,
        new_password: str,
        additional_keyfile_paths: Sequence[Path],
        recovery_code: str,
    ) -> PasswordUpdatedVault:
        """Rotate the password and return a new authenticated session."""
        replacement_vault = UnlockedVault.create(
            vault_path=(vault.vault_path),
            keyfile_path=(vault.keyfile_path),
            password=new_password,
        )

        normalized_recovery_code = recovery_code.strip() or None

        try:
            result = change_vault_password(
                vault_path=(vault.vault_path),
                current_keyfile_path=(vault.keyfile_path),
                current_password=(current_password),
                new_password=new_password,
                additional_keyfile_paths=(additional_keyfile_paths),
                recovery_code=(normalized_recovery_code),
            )
            entries = list_files(
                vault_path=(replacement_vault.vault_path),
                keyfile_path=(replacement_vault.keyfile_path),
                password=(replacement_vault.password_bytes()),
            )
        except Exception:
            replacement_vault.close()
            raise

        return PasswordUpdatedVault(
            vault=replacement_vault,
            entries=entries,
            key_count=result.key_count,
            recovery_updated=(result.recovery_updated),
        )
