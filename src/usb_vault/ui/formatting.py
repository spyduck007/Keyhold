"""Display formatting used by the desktop UI."""

from __future__ import annotations


def format_file_size(size: int) -> str:
    """Format a non-negative byte count for humans."""
    if type(size) is not int:
        raise TypeError("size must be an integer")

    if size < 0:
        raise ValueError("size must not be negative")

    if size < 1_024:
        unit = "byte" if size == 1 else "bytes"
        return f"{size} {unit}"

    units = (
        "KiB",
        "MiB",
        "GiB",
        "TiB",
    )
    value = float(size)

    for unit in units:
        value /= 1_024

        if value < 1_024 or unit == units[-1]:
            return f"{value:.1f} {unit}"

    raise RuntimeError("unable to format file size")
