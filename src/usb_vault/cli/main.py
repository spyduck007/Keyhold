"""Command-line entry point for the USB Vault prototype."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from usb_vault.cli.commands.add import (
    run_add_command,
)
from usb_vault.cli.commands.add_key import (
    run_add_key_command,
)
from usb_vault.cli.commands.change_password import (
    run_change_password_command,
)
from usb_vault.cli.commands.create import (
    run_create_command,
)
from usb_vault.cli.commands.create_recovery import (
    run_create_recovery_command,
)
from usb_vault.cli.commands.delete import (
    run_delete_command,
)
from usb_vault.cli.commands.extract import (
    run_extract_command,
)
from usb_vault.cli.commands.list_files import (
    run_list_command,
)
from usb_vault.cli.commands.list_keys import (
    run_list_keys_command,
)
from usb_vault.cli.commands.recover_usb import (
    run_recover_usb_command,
)
from usb_vault.cli.commands.recovery_unlock import (
    run_recovery_unlock_command,
)
from usb_vault.cli.commands.rename import (
    run_rename_command,
)
from usb_vault.cli.commands.revoke_key import (
    run_revoke_key_command,
)
from usb_vault.cli.commands.unlock import (
    run_unlock_command,
)
from usb_vault.core.errors import (
    VaultError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="usb-vault",
        description=("Create and manage a password-plus-USB encrypted vault."),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    create_parser = subparsers.add_parser(
        "create",
        help=("Create a new empty encrypted vault."),
    )
    _add_vault_and_keyfile_arguments(
        create_parser,
        new_paths=True,
    )

    unlock_parser = subparsers.add_parser(
        "unlock",
        help=("Verify that an existing vault can be unlocked."),
    )
    _add_vault_and_keyfile_arguments(unlock_parser)

    add_parser = subparsers.add_parser(
        "add",
        help=("Add one file to the vault root."),
    )
    _add_vault_and_keyfile_arguments(add_parser)
    add_parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help=("Regular file to encrypt into the vault."),
    )
    add_parser.add_argument(
        "--name",
        help=("Optional filename to store inside the vault."),
    )

    list_parser = subparsers.add_parser(
        "list",
        help=("List files in the encrypted manifest."),
    )
    _add_vault_and_keyfile_arguments(list_parser)

    extract_parser = subparsers.add_parser(
        "extract",
        help=("Extract one file from the vault."),
    )
    _add_vault_and_keyfile_arguments(extract_parser)
    extract_parser.add_argument(
        "--name",
        required=True,
        help=("Stored filename to extract."),
    )
    extract_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=("Exact output file path."),
    )
    extract_parser.add_argument(
        "--overwrite",
        action="store_true",
        help=("Replace an existing output file."),
    )

    delete_parser = subparsers.add_parser(
        "delete",
        help=("Delete one file from the vault."),
    )
    _add_vault_and_keyfile_arguments(delete_parser)
    delete_parser.add_argument(
        "--name",
        required=True,
        help=("Stored filename to delete."),
    )

    rename_parser = subparsers.add_parser(
        "rename",
        help=("Rename one file in the encrypted manifest."),
    )
    _add_vault_and_keyfile_arguments(rename_parser)
    rename_parser.add_argument(
        "--name",
        required=True,
        help=("Current stored filename."),
    )
    rename_parser.add_argument(
        "--new-name",
        required=True,
        help=("New root-level filename."),
    )

    add_key_parser = subparsers.add_parser(
        "add-key",
        help=("Create and register another USB key."),
    )
    _add_vault_and_keyfile_arguments(add_key_parser)
    add_key_parser.add_argument(
        "--new-keyfile",
        type=Path,
        required=True,
        help=("Path for the new independent USB keyfile."),
    )

    keys_parser = subparsers.add_parser(
        "keys",
        help=("List registered USB key IDs."),
    )
    _add_vault_and_keyfile_arguments(keys_parser)

    revoke_key_parser = subparsers.add_parser(
        "revoke-key",
        help=("Revoke a registered non-current USB key."),
    )
    _add_vault_and_keyfile_arguments(revoke_key_parser)
    revoke_key_parser.add_argument(
        "--key-id",
        required=True,
        help=("The 32-character hexadecimal key ID to revoke."),
    )
    revoke_key_parser.add_argument(
        "--yes",
        action="store_true",
        help=("Confirm permanent key revocation."),
    )

    change_password_parser = subparsers.add_parser(
        "change-password",
        help=("Change the password for every registered unlock method."),
    )
    _add_vault_and_keyfile_arguments(change_password_parser)
    change_password_parser.add_argument(
        "--other-keyfile",
        type=Path,
        action="append",
        default=[],
        help=(
            "Another registered USB keyfile. Repeat once for every additional registered USB key."
        ),
    )

    recovery_create_parser = subparsers.add_parser(
        "recovery-create",
        help=("Create the vault's offline recovery code."),
    )
    _add_vault_and_keyfile_arguments(recovery_create_parser)

    recovery_rotate_parser = subparsers.add_parser(
        "recovery-rotate",
        help=("Replace the existing recovery code."),
    )
    _add_vault_and_keyfile_arguments(recovery_rotate_parser)

    recovery_unlock_parser = subparsers.add_parser(
        "recovery-unlock",
        help=("Verify password-plus-recovery access without a USB."),
    )
    recovery_unlock_parser.add_argument(
        "--vault",
        type=Path,
        required=True,
        help=("Path to the .vault file."),
    )

    recover_usb_parser = subparsers.add_parser(
        "recover-usb",
        help=("Create a replacement USB using the password and recovery code."),
    )
    recover_usb_parser.add_argument(
        "--vault",
        type=Path,
        required=True,
        help=("Path to the .vault file."),
    )
    recover_usb_parser.add_argument(
        "--new-keyfile",
        type=Path,
        required=True,
        help=("Path for the recovered USB keyfile."),
    )
    recover_usb_parser.add_argument(
        "--replace-existing-keys",
        action="store_true",
        help=("Revoke every previous USB key slot."),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run the selected command and return an exit code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        vault_path = Path(arguments.vault)

        if arguments.command == "recovery-unlock":
            return run_recovery_unlock_command(
                vault_path=vault_path,
            )

        if arguments.command == "recover-usb":
            return run_recover_usb_command(
                vault_path=vault_path,
                new_keyfile_path=Path(arguments.new_keyfile),
                replace_existing_keys=(arguments.replace_existing_keys),
            )

        keyfile_path = Path(arguments.keyfile)

        if arguments.command == "create":
            return run_create_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
            )

        if arguments.command == "unlock":
            return run_unlock_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
            )

        if arguments.command == "add":
            return run_add_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                source_path=Path(arguments.source),
                stored_name=(arguments.name),
            )

        if arguments.command == "list":
            return run_list_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
            )

        if arguments.command == "extract":
            return run_extract_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                stored_name=(arguments.name),
                output_path=Path(arguments.output),
                overwrite=(arguments.overwrite),
            )

        if arguments.command == "delete":
            return run_delete_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                stored_name=(arguments.name),
            )

        if arguments.command == "rename":
            return run_rename_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                stored_name=(arguments.name),
                new_name=(arguments.new_name),
            )

        if arguments.command == "add-key":
            return run_add_key_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                new_keyfile_path=Path(arguments.new_keyfile),
            )

        if arguments.command == "keys":
            return run_list_keys_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
            )

        if arguments.command == "revoke-key":
            return run_revoke_key_command(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                key_id_hex=(arguments.key_id),
                confirmed=(arguments.yes),
            )

        if arguments.command == "change-password":
            return run_change_password_command(
                vault_path=vault_path,
                keyfile_path=(keyfile_path),
                additional_keyfile_paths=(tuple(arguments.other_keyfile)),
            )

        if arguments.command == "recovery-create":
            return run_create_recovery_command(
                vault_path=vault_path,
                keyfile_path=(keyfile_path),
                replace=False,
            )

        if arguments.command == "recovery-rotate":
            return run_create_recovery_command(
                vault_path=vault_path,
                keyfile_path=(keyfile_path),
                replace=True,
            )

        parser.error("unsupported command")
    except (
        VaultError,
        OSError,
        ValueError,
    ) as error:
        print(
            str(error),
            file=sys.stderr,
        )
        return 1


def _add_vault_and_keyfile_arguments(
    parser: argparse.ArgumentParser,
    *,
    new_paths: bool = False,
) -> None:
    vault_help = "Path for the new .vault file." if new_paths else "Path to the .vault file."
    keyfile_help = "Path for the new USB keyfile." if new_paths else "Path to the USB keyfile."

    parser.add_argument(
        "--vault",
        type=Path,
        required=True,
        help=vault_help,
    )
    parser.add_argument(
        "--keyfile",
        type=Path,
        required=True,
        help=keyfile_help,
    )
