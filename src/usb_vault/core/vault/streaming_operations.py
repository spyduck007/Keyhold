"""Streaming add, list, extract, and delete vault operations."""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import (
    Iterator,
    Sequence,
)
from contextlib import (
    contextmanager,
    suppress,
)
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from usb_vault.core.crypto.payload_encryption import (
    EncryptedPayload,
    encrypt_payload,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    secure_random_bytes,
)
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    VaultOperationError,
)
from usb_vault.core.storage.atomic_save import (
    PRIVATE_FILE_MODE,
    atomic_write_bytes,
    atomic_write_file,
)
from usb_vault.core.storage.streaming_container import (
    BlobEncoding,
    StoredBlob,
    write_streaming_vault,
)
from usb_vault.core.vault.blob import (
    BLOB_ID_LENGTH,
    MAX_BLOB_PLAINTEXT_LENGTH,
    EncryptedBlob,
    decrypt_blob,
)
from usb_vault.core.vault.chunk_stream import (
    DEFAULT_CHUNK_SIZE,
    MAX_PLAINTEXT_LENGTH,
    decrypt_chunk_stream,
    encrypt_chunk_stream,
)
from usb_vault.core.vault.manifest import (
    ENTRY_ID_LENGTH,
    VaultEntry,
    VaultManifest,
    create_vault_entry,
    manifest_associated_data,
    normalize_entry_name,
)
from usb_vault.core.vault.session import (
    SessionBlob,
    VaultSession,
)
from usb_vault.core.vault.unlocker import (
    unlock_vault,
)


@dataclass(frozen=True, slots=True)
class VaultEntrySummary:
    """Non-secret metadata returned after the vault is unlocked."""

    name: str
    size: int


def add_file(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: (str | bytes | bytearray | memoryview),
    source_path: str | Path,
    stored_name: str | None = None,
) -> VaultEntrySummary:
    """Stream one regular file into a version 3 vault."""
    source = Path(source_path)
    entry_name = normalize_entry_name(stored_name or source.name)

    with _open_source_file(source) as (
        source_file,
        source_size,
    ):
        with unlock_vault(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=password,
        ) as session:
            if session.manifest.find_by_name(entry_name) is not None:
                raise EntryExistsError(f"Vault entry already exists: {entry_name}")

            master_key = session.copy_master_key()
            blob_id = _create_unique_blob_id(session)
            temporary_paths: list[Path] = []

            try:
                existing_blobs, paths = _materialize_blob_sources(
                    session,
                    session.blobs,
                )
                temporary_paths.extend(paths)

                (
                    new_blob,
                    new_blob_path,
                ) = _encrypt_source_to_temporary_blob(
                    source_file,
                    plaintext_length=(source_size),
                    parent=(session.vault_path.parent),
                    master_key=(master_key),
                    vault_id=(session.header.vault_id),
                    blob_id=blob_id,
                )
                temporary_paths.append(new_blob_path)

                entry = _create_unique_entry(
                    name=entry_name,
                    size=source_size,
                    blob_id=blob_id,
                    manifest=(session.manifest),
                )
                updated_manifest = session.manifest.add_entry(entry)

                _write_updated_vault(
                    session=session,
                    manifest=(updated_manifest),
                    blobs=(
                        *existing_blobs,
                        new_blob,
                    ),
                    master_key=master_key,
                )
            finally:
                _remove_temporary_paths(temporary_paths)

    return VaultEntrySummary(
        name=entry.name,
        size=entry.size,
    )


def list_files(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: (str | bytes | bytearray | memoryview),
) -> tuple[
    VaultEntrySummary,
    ...,
]:
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
            for entry in (ordered_entries)
        )


def extract_file(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: (str | bytes | bytearray | memoryview),
    stored_name: str,
    destination_path: str | Path,
    overwrite: bool = False,
) -> VaultEntrySummary:
    """Decrypt one entry to an explicit output path."""
    destination = Path(destination_path)

    protected_destinations = {
        Path(vault_path).absolute(),
        Path(keyfile_path).absolute(),
    }

    if destination.absolute() in protected_destinations:
        raise VaultOperationError(
            "The export destination must not replace the vault or USB keyfile."
        )

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

        master_key = session.copy_master_key()

        if isinstance(
            blob,
            EncryptedBlob,
        ):
            plaintext = decrypt_blob(
                blob,
                master_key,
                vault_id=(session.header.vault_id),
            )

            if len(plaintext) != entry.size:
                raise VaultOperationError("Vault entry size does not match its data.")

            atomic_write_bytes(
                destination,
                plaintext,
                overwrite=overwrite,
            )
        elif blob.encoding is BlobEncoding.SINGLE_PAYLOAD:
            plaintext = _decrypt_single_payload_blob(
                blob,
                master_key,
                vault_id=(session.header.vault_id),
            )

            if len(plaintext) != entry.size:
                raise VaultOperationError("Vault entry size does not match its data.")

            atomic_write_bytes(
                destination,
                plaintext,
                overwrite=overwrite,
            )
        else:

            def write_plaintext(
                output: BinaryIO,
            ) -> None:
                with _open_stored_payload(blob) as encrypted:
                    summary = decrypt_chunk_stream(
                        encrypted,
                        output,
                        master_key,
                        vault_id=(session.header.vault_id),
                        blob_id=(blob.blob_id),
                        plaintext_length=(blob.plaintext_length),
                        chunk_size=(blob.chunk_size),
                        require_eof=False,
                    )

                if summary.plaintext_length != entry.size:
                    raise VaultOperationError("Vault entry size does not match its data.")

            atomic_write_file(
                destination,
                write_plaintext,
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
    password: (str | bytes | bytearray | memoryview),
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

        remaining_blobs = tuple(
            blob for blob in session.blobs if (blob.blob_id != removed_entry.blob_id)
        )
        master_key = session.copy_master_key()
        temporary_paths: list[Path] = []

        try:
            stored_blobs, paths = _materialize_blob_sources(
                session,
                remaining_blobs,
            )
            temporary_paths.extend(paths)

            _write_updated_vault(
                session=session,
                manifest=(updated_manifest),
                blobs=stored_blobs,
                master_key=master_key,
            )
        finally:
            _remove_temporary_paths(temporary_paths)

        return VaultEntrySummary(
            name=removed_entry.name,
            size=removed_entry.size,
        )


def _write_updated_vault(
    *,
    session: VaultSession,
    manifest: VaultManifest,
    blobs: Sequence[StoredBlob],
    master_key: bytes,
) -> None:
    encrypted_manifest = encrypt_payload(
        manifest.to_bytes(),
        master_key,
        associated_data=(manifest_associated_data(session.header.vault_id)),
    )

    write_streaming_vault(
        session.vault_path,
        header=session.header,
        encrypted_manifest=(encrypted_manifest),
        blobs=tuple(blobs),
        overwrite=True,
    )


def _materialize_blob_sources(
    session: VaultSession,
    blobs: Sequence[SessionBlob],
) -> tuple[
    tuple[
        StoredBlob,
        ...,
    ],
    tuple[
        Path,
        ...,
    ],
]:
    entry_sizes = {entry.blob_id: entry.size for entry in (session.manifest.entries)}
    stored_blobs: list[StoredBlob] = []
    temporary_paths: list[Path] = []

    try:
        for blob in blobs:
            if isinstance(
                blob,
                StoredBlob,
            ):
                stored_blobs.append(blob)
                continue

            plaintext_length = entry_sizes.get(blob.blob_id)

            if plaintext_length is None:
                raise VaultOperationError("Vault data is incomplete.")

            (
                stored_blob,
                temporary_path,
            ) = _write_legacy_blob_to_temporary_file(
                blob,
                plaintext_length=(plaintext_length),
                parent=(session.vault_path.parent),
            )
            stored_blobs.append(stored_blob)
            temporary_paths.append(temporary_path)
    except Exception:
        _remove_temporary_paths(temporary_paths)
        raise

    return (
        tuple(stored_blobs),
        tuple(temporary_paths),
    )


def _encrypt_source_to_temporary_blob(
    source: BinaryIO,
    *,
    plaintext_length: int,
    parent: Path,
    master_key: bytes,
    vault_id: bytes,
    blob_id: bytes,
) -> tuple[
    StoredBlob,
    Path,
]:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".usb-vault-blob.",
        suffix=".tmp",
        dir=parent,
    )
    temporary_path = Path(temporary_name)

    try:
        os.fchmod(
            file_descriptor,
            PRIVATE_FILE_MODE,
        )

        with os.fdopen(
            file_descriptor,
            "wb",
        ) as output:
            file_descriptor = -1

            summary = encrypt_chunk_stream(
                source,
                output,
                master_key,
                vault_id=vault_id,
                blob_id=blob_id,
                plaintext_length=(plaintext_length),
                chunk_size=(DEFAULT_CHUNK_SIZE),
            )
            output.flush()
            os.fsync(output.fileno())

        return (
            StoredBlob(
                blob_id=blob_id,
                encoding=(BlobEncoding.CHUNK_STREAM),
                plaintext_length=(plaintext_length),
                chunk_size=(summary.chunk_size),
                source_path=(temporary_path),
                payload_offset=0,
                payload_length=(summary.serialized_length),
            ),
            temporary_path,
        )
    except Exception:
        if file_descriptor >= 0:
            os.close(file_descriptor)

        with suppress(FileNotFoundError):
            temporary_path.unlink()

        raise


def _write_legacy_blob_to_temporary_file(
    blob: EncryptedBlob,
    *,
    plaintext_length: int,
    parent: Path,
) -> tuple[
    StoredBlob,
    Path,
]:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".usb-vault-legacy-blob.",
        suffix=".tmp",
        dir=parent,
    )
    temporary_path = Path(temporary_name)

    try:
        os.fchmod(
            file_descriptor,
            PRIVATE_FILE_MODE,
        )

        with os.fdopen(
            file_descriptor,
            "wb",
        ) as output:
            file_descriptor = -1
            output.write(blob.payload.nonce)
            output.write(blob.payload.ciphertext)
            output.flush()
            os.fsync(output.fileno())

        return (
            StoredBlob(
                blob_id=blob.blob_id,
                encoding=(BlobEncoding.SINGLE_PAYLOAD),
                plaintext_length=(plaintext_length),
                chunk_size=0,
                source_path=(temporary_path),
                payload_offset=0,
                payload_length=(AES_GCM_NONCE_LENGTH + len(blob.payload.ciphertext)),
            ),
            temporary_path,
        )
    except Exception:
        if file_descriptor >= 0:
            os.close(file_descriptor)

        with suppress(FileNotFoundError):
            temporary_path.unlink()

        raise


def _decrypt_single_payload_blob(
    blob: StoredBlob,
    master_key: bytes,
    *,
    vault_id: bytes,
) -> bytes:
    if blob.plaintext_length > MAX_BLOB_PLAINTEXT_LENGTH:
        raise VaultOperationError("Legacy single-payload blob exceeds the supported limit.")

    with _open_stored_payload(blob) as source:
        nonce = _read_exact(
            source,
            AES_GCM_NONCE_LENGTH,
        )
        ciphertext = _read_exact(
            source,
            (blob.payload_length - AES_GCM_NONCE_LENGTH),
        )

    return decrypt_blob(
        EncryptedBlob(
            blob_id=blob.blob_id,
            payload=EncryptedPayload(
                nonce=nonce,
                ciphertext=ciphertext,
            ),
        ),
        master_key,
        vault_id=vault_id,
    )


@contextmanager
def _open_source_file(
    path: Path,
) -> Iterator[
    tuple[
        BinaryIO,
        int,
    ]
]:
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

        if not (0 <= file_status.st_size <= MAX_PLAINTEXT_LENGTH):
            raise VaultOperationError("Source file is too large.")

        with os.fdopen(
            file_descriptor,
            "rb",
        ) as source:
            file_descriptor = -1
            yield (
                source,
                file_status.st_size,
            )
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


@contextmanager
def _open_stored_payload(
    blob: StoredBlob,
) -> Iterator[BinaryIO]:
    flags = os.O_RDONLY | getattr(
        os,
        "O_NOFOLLOW",
        0,
    )

    try:
        file_descriptor = os.open(
            blob.source_path,
            flags,
        )
    except OSError as error:
        raise VaultOperationError("Vault data is incomplete.") from error

    try:
        file_status = os.fstat(file_descriptor)

        if not stat.S_ISREG(file_status.st_mode):
            raise VaultOperationError("Vault data is incomplete.")

        payload_end = blob.payload_offset + blob.payload_length

        if payload_end > file_status.st_size:
            raise VaultOperationError("Vault data is incomplete.")

        with os.fdopen(
            file_descriptor,
            "rb",
        ) as source:
            file_descriptor = -1
            source.seek(blob.payload_offset)
            yield source
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


def _read_exact(
    source: BinaryIO,
    length: int,
) -> bytes:
    chunks: list[bytes] = []
    remaining = length

    while remaining:
        chunk = source.read(remaining)

        if not chunk:
            raise VaultOperationError("Vault data is incomplete.")

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def _create_unique_blob_id(
    session: VaultSession,
) -> bytes:
    existing_ids = {blob.blob_id for blob in session.blobs}

    for _ in range(16):
        blob_id = secure_random_bytes(BLOB_ID_LENGTH)

        if blob_id not in existing_ids:
            return blob_id

    raise RuntimeError("unable to generate a unique blob identifier")


def _create_unique_entry(
    *,
    name: str,
    size: int,
    blob_id: bytes,
    manifest: VaultManifest,
) -> VaultEntry:
    existing_ids = {entry.entry_id for entry in (manifest.entries)}

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


def _remove_temporary_paths(
    paths: Sequence[Path],
) -> None:
    for path in paths:
        with suppress(FileNotFoundError):
            path.unlink()
