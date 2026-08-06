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

_HARD_LINK_FALLBACK_ERRNOS = frozenset(
    {
        errno.EINVAL,
        errno.EMLINK,
        errno.EPERM,
        getattr(
            errno,
            "ENOSYS",
            errno.EINVAL,
        ),
        getattr(
            errno,
            "ENOTSUP",
            errno.EINVAL,
        ),
        getattr(
            errno,
            "EOPNOTSUPP",
            errno.EINVAL,
        ),
    }
)


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
            _publish_without_overwrite(
                temporary_path,
                destination,
                mode=mode,
            )

        _fsync_directory(parent)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)

        with suppress(FileNotFoundError):
            temporary_path.unlink()


def _publish_without_overwrite(
    temporary_path: Path,
    destination: Path,
    *,
    mode: int,
) -> None:
    """Publish without replacing an existing destination."""
    try:
        os.link(
            temporary_path,
            destination,
        )
    except FileExistsError:
        raise FileExistsError(f"destination already exists: {destination}") from None
    except OSError as error:
        if error.errno not in _HARD_LINK_FALLBACK_ERRNOS:
            raise

        _publish_with_exclusive_reservation(
            temporary_path,
            destination,
            mode=mode,
        )
    else:
        temporary_path.unlink()


def _publish_with_exclusive_reservation(
    temporary_path: Path,
    destination: Path,
    *,
    mode: int,
) -> None:
    """Publish on filesystems that do not support hard links."""
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(
            os,
            "O_CLOEXEC",
            0,
        )
        | getattr(
            os,
            "O_NOFOLLOW",
            0,
        )
    )

    try:
        reservation_descriptor = os.open(
            destination,
            flags,
            mode,
        )
    except FileExistsError:
        raise FileExistsError(f"destination already exists: {destination}") from None

    reservation_status = os.fstat(reservation_descriptor)

    try:
        current_status = os.stat(
            destination,
            follow_symlinks=False,
        )

        if not os.path.samestat(
            reservation_status,
            current_status,
        ):
            raise FileExistsError(
                f"destination changed while the file was being written: {destination}"
            )

        os.replace(
            temporary_path,
            destination,
        )
    except BaseException:
        _remove_exclusive_reservation(
            destination,
            reservation_status,
        )
        raise
    finally:
        os.close(reservation_descriptor)


def _remove_exclusive_reservation(
    destination: Path,
    reservation_status: os.stat_result,
) -> None:
    """Remove a failed reservation only when it is still ours."""
    try:
        current_status = os.stat(
            destination,
            follow_symlinks=False,
        )
    except OSError:
        return

    if not os.path.samestat(
        reservation_status,
        current_status,
    ):
        return

    with suppress(OSError):
        destination.unlink()


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
