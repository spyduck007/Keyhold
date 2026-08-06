"""CLI command for restoring normal USB access."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

from usb_vault.core.vault.recovery import (
    recover_usb_key,
)


def run_recover_usb_command(
    *,
    vault_path: Path,
    new_keyfile_path: Path,
    replace_existing_keys: bool,
) -> int:
    """Use password plus recovery code to create a new USB key."""
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise ValueError("passwords do not match")

    recovery_code = getpass("Current recovery code: ")

    result = recover_usb_key(
        vault_path=vault_path,
        password=password,
        recovery_code=recovery_code,
        new_keyfile_path=(new_keyfile_path),
        replace_existing_keys=(replace_existing_keys),
    )

    print(f"Recovered USB key created: {new_keyfile_path}")

    if result.replaced_existing_keys:
        print("All previous USB key slots were revoked.")
    else:
        print("Existing USB key slots were preserved.")

    print("The used recovery code was rotated. Store this new code offline:")
    print(result.recovery_code)

    return 0
