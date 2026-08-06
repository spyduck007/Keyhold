"""Tests for atomic private file writes."""

import errno
import os
import stat
from pathlib import Path
from typing import BinaryIO

import pytest

from usb_vault.core.storage.atomic_save import (
    atomic_write_bytes,
    atomic_write_file,
)


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

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "data.bin",
    ]


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


def test_atomic_stream_writer_can_write_multiple_parts(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "stream.bin"

    def write_parts(
        output: BinaryIO,
    ) -> None:
        output.write(b"first")
        output.write(b"-")
        output.write(b"second")

    atomic_write_file(
        destination,
        write_parts,
    )

    assert destination.read_bytes() == b"first-second"
    permissions = stat.S_IMODE(destination.stat().st_mode)
    assert permissions == 0o600


def test_atomic_stream_failure_preserves_existing_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "stream.bin"
    destination.write_bytes(b"original")

    def fail_after_partial_write(
        output: BinaryIO,
    ) -> None:
        output.write(b"partial")
        raise RuntimeError("simulated failure")

    with pytest.raises(
        RuntimeError,
        match="simulated failure",
    ):
        atomic_write_file(
            destination,
            fail_after_partial_write,
            overwrite=True,
        )

    assert destination.read_bytes() == b"original"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "stream.bin",
    ]


def test_atomic_write_falls_back_when_hard_links_are_unsupported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "data.bin"

    def unsupported_link(
        *args: object,
        **kwargs: object,
    ) -> None:
        del args
        del kwargs

        raise OSError(
            errno.ENOTSUP,
            "Operation not supported",
        )

    monkeypatch.setattr(
        os,
        "link",
        unsupported_link,
    )

    atomic_write_bytes(
        destination,
        b"removable drive data",
    )

    assert destination.read_bytes() == b"removable drive data"
    permissions = stat.S_IMODE(destination.stat().st_mode)
    assert permissions == 0o600

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "data.bin",
    ]


def test_hard_link_fallback_does_not_overwrite_racing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "data.bin"

    def racing_link(
        *args: object,
        **kwargs: object,
    ) -> None:
        del args
        del kwargs

        destination.write_bytes(b"racing file")
        raise OSError(
            errno.ENOTSUP,
            "Operation not supported",
        )

    monkeypatch.setattr(
        os,
        "link",
        racing_link,
    )

    with pytest.raises(FileExistsError):
        atomic_write_bytes(
            destination,
            b"must not overwrite",
        )

    assert destination.read_bytes() == b"racing file"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "data.bin",
    ]


def test_hard_link_fallback_cleans_failed_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "data.bin"

    def unsupported_link(
        *args: object,
        **kwargs: object,
    ) -> None:
        del args
        del kwargs

        raise OSError(
            errno.ENOTSUP,
            "Operation not supported",
        )

    def failed_replace(
        *args: object,
        **kwargs: object,
    ) -> None:
        del args
        del kwargs

        raise OSError(
            errno.EIO,
            "simulated replace failure",
        )

    monkeypatch.setattr(
        os,
        "link",
        unsupported_link,
    )
    monkeypatch.setattr(
        os,
        "replace",
        failed_replace,
    )

    with pytest.raises(
        OSError,
        match=("simulated replace failure"),
    ):
        atomic_write_bytes(
            destination,
            b"data",
        )

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
