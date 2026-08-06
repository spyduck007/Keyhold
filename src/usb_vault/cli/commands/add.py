"""CLI command for adding one file to a vault."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.operations import add_file


def run_add_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    source_path: Path,
    stored_name: str | None,
) -> int:
    """Prompt for a password and add one encrypted file."""
    password = getpass("Password: ")
    result = add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        source_path=source_path,
        stored_name=stored_name,
    )

    print(f"Added: {result.name} ({result.size} bytes)")

    return 0
