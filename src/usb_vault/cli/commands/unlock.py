"""CLI command for verifying that a vault can be unlocked."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.unlocker import unlock_vault


def run_unlock_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
) -> int:
    """Prompt for a password and validate a vault unlock."""
    password = getpass("Password: ")

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        print("Vault unlocked successfully.")
        print(f"Entries: {session.entry_count}")

    return 0
