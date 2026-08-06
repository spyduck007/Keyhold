"""CLI command for listing registered USB keys."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.key_management import list_usb_keys


def run_list_keys_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
) -> int:
    """Prompt for a password and list registered key IDs."""
    password = getpass("Password: ")

    keys = list_usb_keys(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    )

    for key in keys:
        marker = " [current]" if key.is_current else ""

        print(f"{key.key_id_hex}{marker}")

    return 0
