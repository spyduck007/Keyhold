"""Atomic private file writes for bytes and streaming callbacks."""

from __future__ import annotations

import errno
import os
import tempfile
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

PRIVATE_FILE_MODE = 0o600

AtomicFileWriter = Callable[[BinaryIO], None]


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
    *,
    overwrite: bool = False,
    mode: int = PRIVATE_FILE_MODE,
) -> None:
    """Write bytes atomically in the destination directory."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")

    def write_data(
        destination: BinaryIO,
    ) -> None:
        destination.write(data)

    atomic_write_file(
        path,
        write_data,
        overwrite=overwrite,
        mode=mode,
    )


def atomic_write_file(
    path: str | Path,
    writer: AtomicFileWriter,
    *,
    overwrite: bool = False,
    mode: int = PRIVATE_FILE_MODE,
) -> None:
    """Atomically publish data produced by a streaming writer callback."""
    if not callable(writer):
        raise TypeError("writer must be callable")

    destination = Path(path)
    parent = destination.parent

    if not parent.exists():
        raise FileNotFoundError(f"parent directory does not exist: {parent}")

    if not parent.is_dir():
        raise NotADirectoryError(f"parent path is not a directory: {parent}")

    if destination.exists() and not overwrite:
        raise FileExistsError(f"destination already exists: {destination}")

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=(f".{destination.name}."),
        suffix=".tmp",
        dir=parent,
    )
    temporary_path = Path(temporary_name)

    try:
        os.fchmod(
            file_descriptor,
            mode,
        )

        with os.fdopen(
            file_descriptor,
            "wb",
        ) as temporary_file:
            file_descriptor = -1
            writer(temporary_file)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if overwrite:
            os.replace(
                temporary_path,
                destination,
            )
        else:
            os.link(
                temporary_path,
                destination,
            )
            temporary_path.unlink()

        _fsync_directory(parent)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)

        with suppress(FileNotFoundError):
            temporary_path.unlink()


def _fsync_directory(
    directory: Path,
) -> None:
    flags = os.O_RDONLY
    directory_descriptor = os.open(
        directory,
        flags,
    )

    try:
        os.fsync(directory_descriptor)
    except OSError as error:
        unsupported_errors = {
            errno.EBADF,
            errno.EINVAL,
            getattr(
                errno,
                "ENOTSUP",
                errno.EINVAL,
            ),
        }

        if error.errno not in unsupported_errors:
            raise
    finally:
        os.close(directory_descriptor)
