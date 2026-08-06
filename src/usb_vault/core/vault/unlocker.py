"""Unlock a serialized vault using a password and USB keyfile."""

from __future__ import annotations

from pathlib import Path

from usb_vault.core.crypto.encryption import unwrap_master_key
from usb_vault.core.crypto.key_derivation import (
    derive_key_encryption_key,
)
from usb_vault.core.crypto.password_kdf import derive_password_key
from usb_vault.core.crypto.payload_encryption import decrypt_payload
from usb_vault.core.errors import UnlockError
from usb_vault.core.storage.reader import (
    read_usb_keyfile,
    read_vault_container,
)
from usb_vault.core.vault.manifest import (
    VaultManifest,
    manifest_associated_data,
)
from usb_vault.core.vault.session import VaultSession


def unlock_vault(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
) -> VaultSession:
    """Unlock a vault or raise one generic authentication error."""
    keyfile = read_usb_keyfile(keyfile_path)
    container = read_vault_container(vault_path)

    slot = container.header.find_password_usb_slot(keyfile.key_id)

    if slot is None:
        raise UnlockError

    password_key = derive_password_key(
        password,
        container.header.argon2_salt,
        container.header.argon2_parameters,
    )
    key_encryption_key = derive_key_encryption_key(
        password_key,
        keyfile.secret,
    )
    master_key = unwrap_master_key(
        slot.wrapped_master_key,
        key_encryption_key,
    )
    manifest_bytes = decrypt_payload(
        container.encrypted_manifest,
        master_key,
        associated_data=(manifest_associated_data(container.header.vault_id)),
    )
    manifest = VaultManifest.from_bytes(manifest_bytes)

    expected_blob_ids = {entry.blob_id for entry in manifest.entries}
    actual_blob_ids = {blob.blob_id for blob in container.blobs}

    if expected_blob_ids != actual_blob_ids:
        raise UnlockError

    return VaultSession.create(
        vault_path=vault_path,
        header=container.header,
        manifest=manifest,
        master_key=master_key,
        blobs=container.blobs,
    )
