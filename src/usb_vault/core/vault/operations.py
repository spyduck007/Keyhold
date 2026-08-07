"""Public file-operation API backed by streaming storage."""

from usb_vault.core.vault.rename import (
    move_folder,
    rename_file,
)
from usb_vault.core.vault.streaming_operations import (
    VaultEntrySummary,
    add_file,
    create_folder,
    delete_file,
    delete_folder,
    extract_file,
    list_files,
)

__all__ = [
    "VaultEntrySummary",
    "add_file",
    "create_folder",
    "delete_file",
    "delete_folder",
    "extract_file",
    "list_files",
    "move_folder",
    "rename_file",
]
