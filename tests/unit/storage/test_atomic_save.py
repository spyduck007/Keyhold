"""Tests for atomic private file writes."""

import os
import stat
from pathlib import Path

import pytest

from usb_vault.core.storage.atomic_save import atomic_write_bytes


def test_atomic_write_creates_private_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data.bin"

    atomic_write_bytes(
        destination,
        b"secret data",
    )

    assert destination.read_bytes() == b"secret data"
    permissions = stat.S_IMODE(destination.stat().st_mode)
    assert permissions == 0o600


def test_atomic_write_refuses_to_overwrite_by_default(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data.bin"
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        atomic_write_bytes(
            destination,
            b"replacement",
        )

    assert destination.read_bytes() == b"original"


def test_atomic_write_can_replace_existing_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data.bin"
    destination.write_bytes(b"original")

    atomic_write_bytes(
        destination,
        b"replacement",
        overwrite=True,
    )

    assert destination.read_bytes() == b"replacement"


def test_atomic_write_leaves_no_temporary_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data.bin"

    atomic_write_bytes(
        destination,
        b"data",
    )

    assert sorted(path.name for path in tmp_path.iterdir()) == ["data.bin"]


def test_atomic_write_requires_existing_parent(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "missing" / "data.bin"

    with pytest.raises(FileNotFoundError):
        atomic_write_bytes(
            destination,
            b"data",
        )


def test_atomic_write_does_not_follow_existing_symlink(
    tmp_path: Path,
) -> None:
    real_file = tmp_path / "real.bin"
    symlink = tmp_path / "link.bin"
    real_file.write_bytes(b"original")
    os.symlink(
        real_file,
        symlink,
    )

    with pytest.raises(FileExistsError):
        atomic_write_bytes(
            symlink,
            b"replacement",
        )

    assert real_file.read_bytes() == b"original"
