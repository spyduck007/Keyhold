"""CLI command for renaming one encrypted vault entry."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.operations import (
    rename_file,
)


def run_rename_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    stored_name: str,
    new_name: str,
) -> int:
    """Prompt for a password and rename one manifest entry."""
    password = getpass("Password: ")
    result = rename_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        stored_name=stored_name,
        new_name=new_name,
    )

    print(f"Renamed: {stored_name} -> {result.name}")

    return 0
