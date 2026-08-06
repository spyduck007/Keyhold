"""Tests for bounded storage readers and writers."""

import os
from pathlib import Path

import pytest

from usb_vault.core.errors import VaultFormatError
from usb_vault.core.keys.keyfile import create_usb_keyfile
from usb_vault.core.storage.reader import (
    read_bytes_limited,
    read_usb_keyfile,
)
from usb_vault.core.storage.writer import write_usb_keyfile


def test_keyfile_writer_and_reader_round_trip(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".authkey"
    keyfile = create_usb_keyfile()

    write_usb_keyfile(
        path,
        keyfile,
    )

    assert read_usb_keyfile(path) == keyfile


def test_bounded_reader_rejects_oversized_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "large.bin"
    path.write_bytes(b"A" * 11)

    with pytest.raises(
        VaultFormatError,
        match=r"^Too large\.$",
    ):
        read_bytes_limited(
            path,
            max_size=10,
            error_message="Too large.",
        )


def test_bounded_reader_rejects_symlink_when_supported(
    tmp_path: Path,
) -> None:
    if not getattr(
        os,
        "O_NOFOLLOW",
        0,
    ):
        pytest.skip("O_NOFOLLOW is unavailable")

    target = tmp_path / "target.bin"
    link = tmp_path / "link.bin"
    target.write_bytes(b"data")
    os.symlink(
        target,
        link,
    )

    with pytest.raises(OSError):
        read_bytes_limited(
            link,
            max_size=100,
            error_message="Invalid file.",
        )
