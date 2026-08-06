"""CLI command for verifying a recovery code."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.recovery import (
    unlock_vault_with_recovery,
)


def run_recovery_unlock_command(
    *,
    vault_path: Path,
) -> int:
    """Prompt for password and recovery code, then validate unlock."""
    password = getpass("Password: ")
    recovery_code = getpass("Recovery code: ")

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=password,
        recovery_code=recovery_code,
    ) as session:
        print("Vault recovery unlock succeeded.")
        print(f"Entries: {session.entry_count}")

    return 0
