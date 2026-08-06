"""High-level add, list, extract, and delete vault operations."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from usb_vault.core.crypto.payload_encryption import encrypt_payload
from usb_vault.core.crypto.random import secure_random_bytes
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    VaultOperationError,
)
from usb_vault.core.storage.atomic_save import atomic_write_bytes
from usb_vault.core.storage.container import VaultContainer
from usb_vault.core.storage.writer import write_vault_container
from usb_vault.core.vault.blob import (
    BLOB_ID_LENGTH,
    MAX_BLOB_PLAINTEXT_LENGTH,
    EncryptedBlob,
    decrypt_blob,
    encrypt_blob,
)
from usb_vault.core.vault.manifest import (
    ENTRY_ID_LENGTH,
    VaultEntry,
    VaultManifest,
    create_vault_entry,
    manifest_associated_data,
    normalize_entry_name,
)
from usb_vault.core.vault.session import VaultSession
from usb_vault.core.vault.unlocker import unlock_vault


@dataclass(frozen=True, slots=True)
class VaultEntrySummary:
    """Non-secret metadata returned after the vault is unlocked."""

    name: str
    size: int


def add_file(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
    source_path: str | Path,
    stored_name: str | None = None,
) -> VaultEntrySummary:
    """Encrypt one regular file into the vault root."""
    source = Path(source_path)
    plaintext = _read_source_file(source)
    entry_name = normalize_entry_name(stored_name or source.name)

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        if session.manifest.find_by_name(entry_name) is not None:
            raise EntryExistsError(f"Vault entry already exists: {entry_name}")

        master_key = session.copy_master_key()
        blob = _create_unique_blob(
            plaintext,
            master_key,
            session=session,
        )
        entry = _create_unique_entry(
            name=entry_name,
            size=len(plaintext),
            blob_id=blob.blob_id,
            manifest=session.manifest,
        )
        updated_manifest = session.manifest.add_entry(entry)
        updated_blobs = (
            *session.blobs,
            blob,
        )

        _write_updated_vault(
            session=session,
            manifest=updated_manifest,
            blobs=updated_blobs,
            master_key=master_key,
        )

    return VaultEntrySummary(
        name=entry.name,
        size=entry.size,
    )


def list_files(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
) -> tuple[VaultEntrySummary, ...]:
    """Return root-level file metadata in display order."""
    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        ordered_entries = sorted(
            session.manifest.entries,
            key=lambda entry: (
                entry.name.casefold(),
                entry.name,
            ),
        )

        return tuple(
            VaultEntrySummary(
                name=entry.name,
                size=entry.size,
            )
            for entry in ordered_entries
        )


def extract_file(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
    stored_name: str,
    destination_path: str | Path,
    overwrite: bool = False,
) -> VaultEntrySummary:
    """Decrypt one vault entry to an explicit output path."""
    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        entry = _require_entry(
            session.manifest,
            stored_name,
        )
        blob = session.find_blob(entry.blob_id)

        if blob is None:
            raise VaultOperationError("Vault data is incomplete.")

        plaintext = decrypt_blob(
            blob,
            session.copy_master_key(),
            vault_id=(session.header.vault_id),
        )

        if len(plaintext) != entry.size:
            raise VaultOperationError("Vault entry size does not match its data.")

        atomic_write_bytes(
            destination_path,
            plaintext,
            overwrite=overwrite,
        )

        return VaultEntrySummary(
            name=entry.name,
            size=entry.size,
        )


def delete_file(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
    stored_name: str,
) -> VaultEntrySummary:
    """Remove one entry and encrypted blob atomically."""
    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        (
            updated_manifest,
            removed_entry,
        ) = session.manifest.remove_entry(stored_name)

        updated_blobs = tuple(
            blob for blob in session.blobs if (blob.blob_id != removed_entry.blob_id)
        )
        master_key = session.copy_master_key()

        _write_updated_vault(
            session=session,
            manifest=updated_manifest,
            blobs=updated_blobs,
            master_key=master_key,
        )

        return VaultEntrySummary(
            name=removed_entry.name,
            size=removed_entry.size,
        )


def _write_updated_vault(
    *,
    session: VaultSession,
    manifest: VaultManifest,
    blobs: tuple[EncryptedBlob, ...],
    master_key: bytes,
) -> None:
    encrypted_manifest = encrypt_payload(
        manifest.to_bytes(),
        master_key,
        associated_data=(manifest_associated_data(session.header.vault_id)),
    )
    updated_container = VaultContainer(
        header=session.header,
        encrypted_manifest=(encrypted_manifest),
        blobs=blobs,
    )

    write_vault_container(
        session.vault_path,
        updated_container,
        overwrite=True,
    )


def _create_unique_blob(
    plaintext: bytes,
    master_key: bytes,
    *,
    session: VaultSession,
) -> EncryptedBlob:
    existing_ids = {blob.blob_id for blob in session.blobs}

    for _ in range(16):
        blob_id = secure_random_bytes(BLOB_ID_LENGTH)

        if blob_id not in existing_ids:
            return encrypt_blob(
                plaintext,
                master_key,
                vault_id=(session.header.vault_id),
                blob_id=blob_id,
            )

    raise RuntimeError("unable to generate a unique blob identifier")


def _create_unique_entry(
    *,
    name: str,
    size: int,
    blob_id: bytes,
    manifest: VaultManifest,
) -> VaultEntry:
    existing_ids = {entry.entry_id for entry in manifest.entries}

    for _ in range(16):
        entry_id = secure_random_bytes(ENTRY_ID_LENGTH)

        if entry_id not in existing_ids:
            return create_vault_entry(
                name=name,
                size=size,
                blob_id=blob_id,
                entry_id=entry_id,
            )

    raise RuntimeError("unable to generate a unique entry identifier")


def _require_entry(
    manifest: VaultManifest,
    name: str,
) -> VaultEntry:
    entry = manifest.find_by_name(name)

    if entry is None:
        normalized_name = normalize_entry_name(name)
        raise EntryNotFoundError(f"Vault entry not found: {normalized_name}")

    return entry


def _read_source_file(
    path: Path,
) -> bytes:
    flags = os.O_RDONLY | getattr(
        os,
        "O_NOFOLLOW",
        0,
    )

    try:
        file_descriptor = os.open(
            path,
            flags,
        )
    except OSError as error:
        raise VaultOperationError(f"Unable to read source file: {path}") from error

    try:
        file_status = os.fstat(file_descriptor)

        if not stat.S_ISREG(file_status.st_mode):
            raise VaultOperationError("Source path must be a regular file.")

        if file_status.st_size > MAX_BLOB_PLAINTEXT_LENGTH:
            raise VaultOperationError(
                f"Source file exceeds the {MAX_BLOB_PLAINTEXT_LENGTH}-byte prototype limit."
            )

        chunks: list[bytes] = []
        total_size = 0

        while True:
            chunk = os.read(
                file_descriptor,
                65_536,
            )

            if not chunk:
                break

            chunks.append(chunk)
            total_size += len(chunk)

            if total_size > MAX_BLOB_PLAINTEXT_LENGTH:
                raise VaultOperationError(
                    f"Source file exceeds the {MAX_BLOB_PLAINTEXT_LENGTH}-byte prototype limit."
                )

        return b"".join(chunks)
    finally:
        os.close(file_descriptor)
