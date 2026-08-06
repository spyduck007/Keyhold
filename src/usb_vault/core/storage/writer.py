"""Writers for serialized vault and USB keyfile structures."""

from __future__ import annotations

from pathlib import Path

from usb_vault.core.keys.keyfile import UsbKeyfile
from usb_vault.core.storage.atomic_save import atomic_write_bytes
from usb_vault.core.storage.container import VaultContainer


def write_usb_keyfile(
    path: str | Path,
    keyfile: UsbKeyfile,
    *,
    overwrite: bool = False,
) -> None:
    """Serialize and atomically write a USB keyfile."""
    if not isinstance(keyfile, UsbKeyfile):
        raise TypeError("keyfile must be UsbKeyfile")

    atomic_write_bytes(
        path,
        keyfile.to_bytes(),
        overwrite=overwrite,
    )


def write_vault_container(
    path: str | Path,
    container: VaultContainer,
    *,
    overwrite: bool = False,
) -> None:
    """Serialize and atomically write a vault container."""
    if not isinstance(container, VaultContainer):
        raise TypeError("container must be VaultContainer")

    atomic_write_bytes(
        path,
        container.to_bytes(),
        overwrite=overwrite,
    )
