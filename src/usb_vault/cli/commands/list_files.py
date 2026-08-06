"""CLI command for listing files in a vault."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.operations import list_files


def run_list_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
) -> int:
    """Prompt for a password and list manifest metadata."""
    password = getpass("Password: ")
    entries = list_files(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    )

    if not entries:
        print("Vault is empty.")
        return 0

    for entry in entries:
        print(f"{entry.name}\t{entry.size} bytes")

    return 0
