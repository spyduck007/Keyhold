"""CLI command for creating a new empty vault."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.creator import create_vault


def run_create_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
) -> int:
    """Prompt for a password and create a new vault."""
    password = getpass("Create password: ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise ValueError("passwords do not match")

    if not password:
        raise ValueError("password must not be empty")

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    )

    print(f"Vault created: {vault_path}")
    print(f"USB keyfile created: {keyfile_path}")

    return 0
