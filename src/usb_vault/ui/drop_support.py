"""Helpers for desktop file drag-and-drop."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData


def local_regular_file_paths(
    mime_data: QMimeData,
) -> tuple[Path, ...]:
    """Return unique local regular files from dropped data."""
    if not isinstance(
        mime_data,
        QMimeData,
    ):
        raise TypeError("mime_data must be QMimeData")

    if not mime_data.hasUrls():
        return ()

    paths: list[Path] = []
    seen: set[Path] = set()

    for url in mime_data.urls():
        if not url.isLocalFile():
            continue

        path = Path(url.toLocalFile())

        if not path.is_file() or path.is_symlink() or path in seen:
            continue

        seen.add(path)
        paths.append(path)

    return tuple(paths)
