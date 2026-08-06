"""Tests for desktop display formatting."""

import pytest

from usb_vault.ui.formatting import (
    format_file_size,
)


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 bytes"),
        (1, "1 byte"),
        (999, "999 bytes"),
        (1_024, "1.0 KiB"),
        (1_536, "1.5 KiB"),
        (1_048_576, "1.0 MiB"),
        (1_073_741_824, "1.0 GiB"),
    ],
)
def test_format_file_size(
    size: int,
    expected: str,
) -> None:
    assert format_file_size(size) == expected


def test_negative_size_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="must not be negative",
    ):
        format_file_size(-1)
