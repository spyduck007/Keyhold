"""Metadata-only encrypted vault entry renaming."""

from __future__ import annotations

from pathlib import Path

from usb_vault.core.crypto.payload_encryption import (
    decrypt_payload,
    encrypt_payload,
)
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    VaultError,
    VaultOperationError,
)
from usb_vault.core.storage.container import (
    VaultContainer,
)
from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.storage.writer import (
    write_vault_container,
)
from usb_vault.core.vault.manifest import (
    VaultEntry,
    VaultManifest,
    manifest_associated_data,
    normalize_entry_name,
)
from usb_vault.core.vault.streaming_operations import (
    VaultEntrySummary,
)
from usb_vault.core.vault.unlocker import (
    unlock_vault,
)


def rename_file(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: (str | bytes | bytearray | memoryview),
    stored_name: str,
    new_name: str,
) -> VaultEntrySummary:
    """Rename one manifest entry without re-encrypting its file data."""
    normalized_new_name = normalize_entry_name(new_name)

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        existing = session.manifest.find_by_name(stored_name)

        if existing is None:
            normalized_stored_name = normalize_entry_name(stored_name)
            raise EntryNotFoundError(f"Vault entry not found: {normalized_stored_name}")

        conflict = session.manifest.find_by_name(normalized_new_name)

        if conflict is not None and conflict.entry_id != existing.entry_id:
            raise EntryExistsError(f"Vault entry already exists: {normalized_new_name}")

        if normalized_new_name == existing.name:
            return VaultEntrySummary(
                name=existing.name,
                size=existing.size,
            )

        renamed_entry = VaultEntry(
            entry_id=existing.entry_id,
            blob_id=existing.blob_id,
            name=normalized_new_name,
            size=existing.size,
        )
        updated_manifest = VaultManifest(
            entries=tuple(
                renamed_entry if entry.entry_id == existing.entry_id else entry
                for entry in (session.manifest.entries)
            )
        )

        master_key = session.copy_master_key()
        current_container = read_vault_container(session.vault_path)

        _verify_unchanged_container(
            container=current_container,
            expected_header=(session.header),
            expected_manifest=(session.manifest),
            master_key=master_key,
        )

        encrypted_manifest = encrypt_payload(
            updated_manifest.to_bytes(),
            master_key,
            associated_data=(manifest_associated_data(session.header.vault_id)),
        )

        write_vault_container(
            session.vault_path,
            VaultContainer(
                header=session.header,
                encrypted_manifest=(encrypted_manifest),
                blobs=(current_container.blobs),
                storage_version=(current_container.storage_version),
            ),
            overwrite=True,
        )

        return VaultEntrySummary(
            name=renamed_entry.name,
            size=renamed_entry.size,
        )


def _verify_unchanged_container(
    *,
    container: VaultContainer,
    expected_header: object,
    expected_manifest: VaultManifest,
    master_key: bytes,
) -> None:
    """Reject an external vault mutation detected during rename."""
    if container.header != expected_header:
        raise VaultOperationError("Vault changed during rename.")

    try:
        current_manifest = VaultManifest.from_bytes(
            decrypt_payload(
                container.encrypted_manifest,
                master_key,
                associated_data=(manifest_associated_data(container.header.vault_id)),
            )
        )
    except VaultError as error:
        raise VaultOperationError("Vault changed during rename.") from error

    if current_manifest != expected_manifest:
        raise VaultOperationError("Vault changed during rename.")

    manifest_blob_ids = {entry.blob_id for entry in (current_manifest.entries)}
    container_blob_ids = {blob.blob_id for blob in container.blobs}

    if manifest_blob_ids != container_blob_ids:
        raise VaultOperationError("Vault data is incomplete.")
