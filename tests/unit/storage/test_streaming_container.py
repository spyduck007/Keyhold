"""Tests for version 3 streaming container indexing and copying."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from usb_vault.core.crypto.encryption import (
    AES_GCM_TAG_LENGTH,
    WrappedMasterKey,
)
from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.crypto.payload_encryption import (
    EncryptedPayload,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    ARGON2_SALT_LENGTH,
)
from usb_vault.core.errors import (
    VaultFormatError,
)
from usb_vault.core.keys.keyfile import (
    KEY_ID_LENGTH,
)
from usb_vault.core.storage.format import (
    VAULT_ID_LENGTH,
    PasswordUsbKeySlot,
    VaultHeader,
)
from usb_vault.core.storage.streaming_container import (
    STREAMING_BLOB_PREFIX,
    STREAMING_CONTAINER_MAGIC,
    STREAMING_CONTAINER_PREFIX,
    BlobEncoding,
    StoredBlob,
    StreamingVaultIndex,
    read_streaming_vault_index,
    write_streaming_vault,
)
from usb_vault.core.vault.chunk_stream import (
    BLOB_ID_LENGTH,
    describe_chunk_stream,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def _header() -> VaultHeader:
    return VaultHeader(
        vault_id=(b"V" * VAULT_ID_LENGTH),
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=(TEST_PARAMETERS),
        key_slots=(
            PasswordUsbKeySlot(
                key_id=(b"K" * KEY_ID_LENGTH),
                wrapped_master_key=(
                    WrappedMasterKey(
                        nonce=(b"N" * AES_GCM_NONCE_LENGTH),
                        ciphertext=(b"W" * 48),
                    )
                ),
            ),
        ),
    )


def _manifest_payload() -> EncryptedPayload:
    return EncryptedPayload(
        nonce=(b"M" * AES_GCM_NONCE_LENGTH),
        ciphertext=(b"C" * 32),
    )


def _single_payload(
    plaintext_length: int,
) -> bytes:
    return b"Q" * AES_GCM_NONCE_LENGTH + b"D" * (plaintext_length + AES_GCM_TAG_LENGTH)


def _stored_single_blob(
    source_path: Path,
    *,
    blob_id: bytes = (b"B" * BLOB_ID_LENGTH),
    plaintext_length: int = 20,
    payload_offset: int = 0,
) -> StoredBlob:
    return StoredBlob(
        blob_id=blob_id,
        encoding=(BlobEncoding.SINGLE_PAYLOAD),
        plaintext_length=(plaintext_length),
        chunk_size=0,
        source_path=source_path,
        payload_offset=(payload_offset),
        payload_length=(AES_GCM_NONCE_LENGTH + plaintext_length + AES_GCM_TAG_LENGTH),
    )


def test_streaming_container_round_trip_copies_payload_range(
    tmp_path: Path,
) -> None:
    payload = _single_payload(20)
    source_path = tmp_path / "payload-source.bin"
    source_path.write_bytes(b"before" + payload + b"after")
    destination = tmp_path / "Private.vault"

    write_streaming_vault(
        destination,
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
        blobs=(
            _stored_single_blob(
                source_path,
                payload_offset=(len(b"before")),
            ),
        ),
    )

    restored = read_streaming_vault_index(destination)

    assert restored.header == _header()
    assert restored.encrypted_manifest == _manifest_payload()
    assert len(restored.blobs) == 1

    restored_blob = restored.blobs[0]

    assert restored_blob.encoding is BlobEncoding.SINGLE_PAYLOAD
    assert restored_blob.plaintext_length == 20

    with destination.open("rb") as vault_file:
        vault_file.seek(restored_blob.payload_offset)
        copied_payload = vault_file.read(restored_blob.payload_length)

    assert copied_payload == payload


def test_writer_sorts_blobs_by_identifier(
    tmp_path: Path,
) -> None:
    first_payload = _single_payload(1)
    second_payload = _single_payload(2)
    first_source = tmp_path / "first.bin"
    second_source = tmp_path / "second.bin"
    first_source.write_bytes(first_payload)
    second_source.write_bytes(second_payload)
    destination = tmp_path / "Private.vault"

    later_id = b"Z" * BLOB_ID_LENGTH
    earlier_id = b"A" * BLOB_ID_LENGTH

    write_streaming_vault(
        destination,
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
        blobs=(
            _stored_single_blob(
                first_source,
                blob_id=later_id,
                plaintext_length=1,
            ),
            _stored_single_blob(
                second_source,
                blob_id=earlier_id,
                plaintext_length=2,
            ),
        ),
    )

    restored = read_streaming_vault_index(destination)

    assert [blob.blob_id for blob in restored.blobs] == [
        earlier_id,
        later_id,
    ]


def test_chunk_stream_layout_is_indexed(
    tmp_path: Path,
) -> None:
    summary = describe_chunk_stream(
        9,
        chunk_size=4,
    )
    source_path = tmp_path / "chunked.bin"
    source_path.write_bytes(b"X" * summary.serialized_length)
    destination = tmp_path / "Private.vault"

    write_streaming_vault(
        destination,
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
        blobs=(
            StoredBlob(
                blob_id=(b"B" * BLOB_ID_LENGTH),
                encoding=(BlobEncoding.CHUNK_STREAM),
                plaintext_length=9,
                chunk_size=4,
                source_path=(source_path),
                payload_offset=0,
                payload_length=(summary.serialized_length),
            ),
        ),
    )

    restored_blob = read_streaming_vault_index(destination).blobs[0]

    assert restored_blob.encoding is BlobEncoding.CHUNK_STREAM
    assert restored_blob.chunk_size == 4
    assert restored_blob.payload_length == summary.serialized_length


def test_duplicate_blob_ids_are_rejected(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(_single_payload(1))
    blob = _stored_single_blob(
        payload_path,
        plaintext_length=1,
    )

    with pytest.raises(
        ValueError,
        match=("identifiers must be unique"),
    ):
        StreamingVaultIndex(
            path=(tmp_path / "Private.vault"),
            header=_header(),
            encrypted_manifest=(_manifest_payload()),
            blobs=(
                blob,
                blob,
            ),
        )


def test_invalid_chunk_stream_length_is_rejected(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(b"X" * 100)

    with pytest.raises(
        ValueError,
        match="payload length",
    ):
        StoredBlob(
            blob_id=(b"B" * BLOB_ID_LENGTH),
            encoding=(BlobEncoding.CHUNK_STREAM),
            plaintext_length=9,
            chunk_size=4,
            source_path=(payload_path),
            payload_offset=0,
            payload_length=100,
        )


def test_trailing_data_is_rejected(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "Private.vault"

    write_streaming_vault(
        destination,
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
    )

    with destination.open("ab") as output:
        output.write(b"extra")

    with pytest.raises(VaultFormatError):
        read_streaming_vault_index(destination)


def test_truncated_blob_payload_is_rejected(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(_single_payload(20))
    destination = tmp_path / "Private.vault"

    write_streaming_vault(
        destination,
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
        blobs=(_stored_single_blob(payload_path),),
    )

    with destination.open("r+b") as output:
        output.truncate((destination.stat().st_size - 1))

    with pytest.raises(VaultFormatError):
        read_streaming_vault_index(destination)


def test_invalid_magic_is_rejected(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "Private.vault"
    destination.write_bytes(b"not-vault")

    with pytest.raises(VaultFormatError):
        read_streaming_vault_index(destination)


def test_failed_payload_copy_preserves_existing_destination(
    tmp_path: Path,
) -> None:
    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(_single_payload(20))
    blob = _stored_single_blob(payload_path)
    payload_path.write_bytes(b"too short")

    destination = tmp_path / "Private.vault"
    destination.write_bytes(b"original")

    with pytest.raises(VaultFormatError):
        write_streaming_vault(
            destination,
            header=_header(),
            encrypted_manifest=(_manifest_payload()),
            blobs=(blob,),
            overwrite=True,
        )

    assert destination.read_bytes() == b"original"
    assert (
        sorted(path.name for path in tmp_path.iterdir() if path.name.startswith(".Private.vault."))
        == []
    )


def test_large_sparse_vault_is_indexed_without_whole_file_limit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "large.vault"
    header_bytes = _header().to_bytes()
    manifest = _manifest_payload()
    plaintext_length = 300 * 1_048_576
    payload_length = AES_GCM_NONCE_LENGTH + plaintext_length + AES_GCM_TAG_LENGTH

    with destination.open("wb") as output:
        output.write(
            STREAMING_CONTAINER_PREFIX.pack(
                STREAMING_CONTAINER_MAGIC,
                len(header_bytes),
                len(manifest.ciphertext),
                1,
            )
        )
        output.write(header_bytes)
        output.write(manifest.nonce)
        output.write(manifest.ciphertext)
        output.write(
            STREAMING_BLOB_PREFIX.pack(
                (b"B" * BLOB_ID_LENGTH),
                int(BlobEncoding.SINGLE_PAYLOAD),
                plaintext_length,
                0,
                payload_length,
            )
        )
        output.seek(
            payload_length - 1,
            os.SEEK_CUR,
        )
        output.write(b"\0")

    restored = read_streaming_vault_index(destination)

    assert destination.stat().st_size > 268_435_456
    assert restored.blobs[0].payload_length == payload_length
