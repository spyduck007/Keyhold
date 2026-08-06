"""Bounded readers for vault and USB keyfile data."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from usb_vault.core.errors import VaultFormatError
from usb_vault.core.keys.keyfile import UsbKeyfile
from usb_vault.core.storage.container import VaultContainer

MAX_KEYFILE_SIZE = 65_536
MAX_VAULT_CONTAINER_SIZE = 18_000_000


def read_usb_keyfile(
    path: str | Path,
) -> UsbKeyfile:
    """Read and parse one bounded USB keyfile."""
    data = read_bytes_limited(
        path,
        max_size=MAX_KEYFILE_SIZE,
        error_message="Invalid USB keyfile.",
    )

    return UsbKeyfile.from_bytes(data)


def read_vault_container(
    path: str | Path,
) -> VaultContainer:
    """Read and parse one bounded vault container."""
    data = read_bytes_limited(
        path,
        max_size=MAX_VAULT_CONTAINER_SIZE,
        error_message="Invalid vault container.",
    )

    return VaultContainer.from_bytes(data)


def read_bytes_limited(
    path: str | Path,
    *,
    max_size: int,
    error_message: str,
) -> bytes:
    """Read a regular file without following its final symlink."""
    if max_size <= 0:
        raise ValueError("max_size must be greater than zero")

    file_path = Path(path)
    flags = os.O_RDONLY | getattr(
        os,
        "O_NOFOLLOW",
        0,
    )
    file_descriptor = os.open(
        file_path,
        flags,
    )

    try:
        file_status = os.fstat(file_descriptor)

        if not stat.S_ISREG(file_status.st_mode):
            raise VaultFormatError(error_message)

        if file_status.st_size > max_size:
            raise VaultFormatError(error_message)

        chunks: list[bytes] = []
        total_size = 0

        while True:
            read_size = min(
                65_536,
                max_size + 1 - total_size,
            )
            chunk = os.read(
                file_descriptor,
                read_size,
            )

            if not chunk:
                break

            chunks.append(chunk)
            total_size += len(chunk)

            if total_size > max_size:
                raise VaultFormatError(error_message)

        return b"".join(chunks)
    finally:
        os.close(file_descriptor)
