"""Tests for desktop drag-and-drop filtering."""

from pathlib import Path

from PySide6.QtCore import (
    QMimeData,
    QUrl,
)

from usb_vault.ui.drop_support import (
    local_regular_file_paths,
)


def test_local_regular_files_are_returned(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.bin"

    first.write_text(
        "first",
        encoding="utf-8",
    )
    second.write_bytes(b"second")

    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(first)),
            QUrl.fromLocalFile(str(second)),
        ]
    )

    assert local_regular_file_paths(mime_data) == (
        first,
        second,
    )


def test_directories_and_remote_urls_are_ignored(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "folder"
    directory.mkdir()

    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(directory)),
            QUrl("https://example.com/file.txt"),
        ]
    )

    assert local_regular_file_paths(mime_data) == ()


def test_duplicate_paths_are_removed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text(
        "data",
        encoding="utf-8",
    )

    url = QUrl.fromLocalFile(str(source))
    mime_data = QMimeData()
    mime_data.setUrls(
        [
            url,
            url,
        ]
    )

    assert local_regular_file_paths(mime_data) == (source,)
