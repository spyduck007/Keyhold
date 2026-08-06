"""CLI command for registering another USB key."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.key_management import add_usb_key


def run_add_key_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    new_keyfile_path: Path,
) -> int:
    """Prompt for a password and create another USB key."""
    password = getpass("Password: ")

    result = add_usb_key(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        new_keyfile_path=new_keyfile_path,
    )

    print(f"USB key created: {new_keyfile_path}")
    print(f"Key ID: {result.key_id_hex}")

    return 0
