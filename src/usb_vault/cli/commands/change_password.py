"""CLI command for rotating a vault password."""

from __future__ import annotations

from collections.abc import Sequence
from getpass import getpass
from pathlib import Path

from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.vault.password_management import (
    change_vault_password,
)


def run_change_password_command(
    *,
    vault_path: Path,
    keyfile_path: Path,
    additional_keyfile_paths: Sequence[Path],
) -> int:
    """Prompt for credentials and rotate every unlock slot."""
    current_password = getpass("Current password: ")

    container = read_vault_container(vault_path)
    recovery_code = (
        getpass("Current recovery code: ") if (container.header.recovery_slots) else None
    )

    new_password = getpass("New password: ")
    confirmation = getpass("Confirm new password: ")

    if new_password != confirmation:
        raise ValueError("new passwords do not match")

    result = change_vault_password(
        vault_path=vault_path,
        current_keyfile_path=(keyfile_path),
        current_password=(current_password),
        new_password=new_password,
        additional_keyfile_paths=(additional_keyfile_paths),
        recovery_code=recovery_code,
    )

    print("Password changed successfully.")
    print(f"Updated USB key slots: {result.key_count}")

    if result.recovery_updated:
        print("The existing recovery code was updated for the new password.")

    return 0
