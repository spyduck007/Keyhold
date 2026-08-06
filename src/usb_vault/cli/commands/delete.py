"""CLI command for deleting one file from a vault."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.operations import delete_file


def run_delete_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    stored_name: str,
) -> int:
    """Prompt for a password and delete one encrypted file."""
    password = getpass("Password: ")
    result = delete_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        stored_name=stored_name,
    )

    print(f"Deleted: {result.name}")

    return 0
