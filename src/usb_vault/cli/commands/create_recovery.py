"""CLI commands for creating and rotating recovery codes."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.recovery import (
    create_recovery_code,
)


def run_create_recovery_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    replace: bool,
) -> int:
    """Create or rotate a password-protected recovery code."""
    password = getpass("Password: ")

    result = create_recovery_code(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
        replace=replace,
    )

    action = "rotated" if result.replaced_existing else "created"

    print(f"Recovery code {action} successfully.")
    print("Store this code offline. It will not be shown again:")
    print(result.recovery_code)

    return 0
