"""CLI command for extracting one file from a vault."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.operations import extract_file


def run_extract_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    stored_name: str,
    output_path: Path,
    overwrite: bool,
) -> int:
    """Prompt for a password and extract one file."""
    password = getpass("Password: ")
    result = extract_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        stored_name=stored_name,
        destination_path=output_path,
        overwrite=overwrite,
    )

    print(f"Extracted: {result.name} -> {output_path}")

    return 0
