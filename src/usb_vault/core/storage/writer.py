"""Writers for USB keyfiles and versioned vault containers."""

from __future__ import annotations

from pathlib import Path

from usb_vault.core.keys.keyfile import (
    UsbKeyfile,
)
from usb_vault.core.storage.atomic_save import (
    atomic_write_bytes,
)
from usb_vault.core.storage.container import (
    VaultContainer,
)
from usb_vault.core.storage.streaming_container import (
    StoredBlob,
    write_streaming_vault,
)


def write_usb_keyfile(
    path: str | Path,
    keyfile: UsbKeyfile,
    *,
    overwrite: bool = False,
) -> None:
    """Serialize and atomically write a USB keyfile."""
    if not isinstance(
        keyfile,
        UsbKeyfile,
    ):
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
    """Atomically write a legacy or streaming vault container."""
    if not isinstance(
        container,
        VaultContainer,
    ):
        raise TypeError("container must be VaultContainer")

    if container.storage_version == 3:
        streaming_blobs: list[StoredBlob] = []

        for blob in container.blobs:
            if not isinstance(
                blob,
                StoredBlob,
            ):
                raise TypeError("version 3 vaults require stored blob records")

            streaming_blobs.append(blob)

        write_streaming_vault(
            path,
            header=container.header,
            encrypted_manifest=(container.encrypted_manifest),
            blobs=tuple(streaming_blobs),
            overwrite=overwrite,
        )
        return

    atomic_write_bytes(
        path,
        container.to_bytes(),
        overwrite=overwrite,
    )
