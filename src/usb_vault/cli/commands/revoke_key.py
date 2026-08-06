"""CLI command for revoking a registered USB key."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.key_management import (
    parse_key_id_hex,
    revoke_usb_key,
)


def run_revoke_key_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    key_id_hex: str,
    confirmed: bool,
) -> int:
    """Prompt for a password and revoke a non-current key."""
    if not confirmed:
        raise ValueError("Pass --yes to confirm USB key revocation.")

    target_key_id = parse_key_id_hex(key_id_hex)
    password = getpass("Password: ")

    result = revoke_usb_key(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        target_key_id=target_key_id,
    )

    print(f"Revoked USB key: {result.key_id_hex}")

    return 0
