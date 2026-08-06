"""Public file-operation API backed by streaming storage."""

from usb_vault.core.vault.streaming_operations import (
    VaultEntrySummary,
    add_file,
    delete_file,
    extract_file,
    list_files,
)

__all__ = [
    "VaultEntrySummary",
    "add_file",
    "delete_file",
    "extract_file",
    "list_files",
]
