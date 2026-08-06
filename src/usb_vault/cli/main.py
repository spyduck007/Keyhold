"""Command-line entry point for the USB Vault prototype."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from usb_vault.cli.commands.create import run_create_command
from usb_vault.cli.commands.unlock import run_unlock_command
from usb_vault.core.errors import VaultError


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="usb-vault",
        description=("Create and unlock a password-plus-USB encrypted vault."),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    create_parser = subparsers.add_parser(
        "create",
        help="Create a new empty encrypted vault.",
    )
    create_parser.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Path for the new .vault file.",
    )
    create_parser.add_argument(
        "--keyfile",
        type=Path,
        required=True,
        help="Path for the new USB keyfile.",
    )

    unlock_parser = subparsers.add_parser(
        "unlock",
        help=("Verify that an existing vault can be unlocked."),
    )
    unlock_parser.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Path to the .vault file.",
    )
    unlock_parser.add_argument(
        "--keyfile",
        type=Path,
        required=True,
        help="Path to the USB keyfile.",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run the selected command and return a process exit code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        vault_path = Path(arguments.vault)
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

    return 2
