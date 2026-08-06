"""Bounded authenticated chunk encryption for large vault blobs."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO

from usb_vault.core.crypto.encryption import AES_GCM_TAG_LENGTH
from usb_vault.core.crypto.payload_encryption import (
    EncryptedPayload,
    decrypt_payload,
    encrypt_payload,
)
from usb_vault.core.crypto.random import AES_GCM_NONCE_LENGTH
from usb_vault.core.errors import (
    VaultFormatError,
    VaultOperationError,
)
from usb_vault.core.storage.format import VAULT_ID_LENGTH

BLOB_ID_LENGTH = 16
DEFAULT_CHUNK_SIZE = 1_048_576
MAX_CHUNK_SIZE = 16_777_216
MAX_CHUNK_COUNT = (1 << 32) - 1
MAX_PLAINTEXT_LENGTH = (1 << 63) - 1

CHUNK_STREAM_AAD_PREFIX = b"USBVAULT|file-blob-chunk|v1|"
CHUNK_AAD_FIELDS = struct.Struct(">QQIII")
CHUNK_RECORD_PREFIX = struct.Struct(f">II{AES_GCM_NONCE_LENGTH}sI")

INVALID_CHUNK_STREAM_MESSAGE = "Invalid encrypted chunk stream."
SOURCE_CHANGED_MESSAGE = "Source file changed during encryption."


@dataclass(frozen=True, slots=True)
class ChunkStreamSummary:
    """Public size metadata describing one encrypted chunk stream."""

    plaintext_length: int
    chunk_size: int
    chunk_count: int
    serialized_length: int

    def __post_init__(self) -> None:
        _require_plaintext_length(self.plaintext_length)
        _require_chunk_size(self.chunk_size)

        expected_count = chunk_count_for_plaintext_length(
            self.plaintext_length,
            chunk_size=self.chunk_size,
        )

        if self.chunk_count != expected_count:
            raise ValueError("chunk_count does not match the plaintext length")

        expected_serialized_length = self.plaintext_length + self.chunk_count * (
            CHUNK_RECORD_PREFIX.size + AES_GCM_TAG_LENGTH
        )

        if self.serialized_length != expected_serialized_length:
            raise ValueError("serialized_length does not match the chunk stream")


def describe_chunk_stream(
    plaintext_length: int,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> ChunkStreamSummary:
    """Calculate the authenticated chunk layout for one blob."""
    _require_plaintext_length(plaintext_length)
    _require_chunk_size(chunk_size)

    chunk_count = chunk_count_for_plaintext_length(
        plaintext_length,
        chunk_size=chunk_size,
    )
    serialized_length = plaintext_length + chunk_count * (
        CHUNK_RECORD_PREFIX.size + AES_GCM_TAG_LENGTH
    )

    return ChunkStreamSummary(
        plaintext_length=plaintext_length,
        chunk_size=chunk_size,
        chunk_count=chunk_count,
        serialized_length=serialized_length,
    )


def chunk_count_for_plaintext_length(
    plaintext_length: int,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """Return the count, including an authenticated empty chunk."""
    _require_plaintext_length(plaintext_length)
    _require_chunk_size(chunk_size)

    chunk_count = max(
        1,
        (plaintext_length + chunk_size - 1) // chunk_size,
    )

    if chunk_count > MAX_CHUNK_COUNT:
        raise ValueError("plaintext requires too many chunks")

    return chunk_count


def encrypt_chunk_stream(
    source: BinaryIO,
    destination: BinaryIO,
    master_key: bytes,
    *,
    vault_id: bytes,
    blob_id: bytes,
    plaintext_length: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> ChunkStreamSummary:
    """Encrypt exactly one known-length source into chunk records."""
    summary = describe_chunk_stream(
        plaintext_length,
        chunk_size=chunk_size,
    )

    for chunk_index in range(summary.chunk_count):
        expected_plaintext_length = _chunk_plaintext_length(
            summary,
            chunk_index,
        )
        plaintext = _read_source_exact(
            source,
            expected_plaintext_length,
        )
        associated_data = chunk_associated_data(
            vault_id,
            blob_id,
            plaintext_length=(summary.plaintext_length),
            chunk_size=(summary.chunk_size),
            chunk_count=(summary.chunk_count),
            chunk_index=chunk_index,
            chunk_plaintext_length=(expected_plaintext_length),
        )
        payload = encrypt_payload(
            plaintext,
            master_key,
            associated_data=associated_data,
        )
        prefix = CHUNK_RECORD_PREFIX.pack(
            chunk_index,
            expected_plaintext_length,
            payload.nonce,
            len(payload.ciphertext),
        )

        _write_all(
            destination,
            prefix,
        )
        _write_all(
            destination,
            payload.ciphertext,
        )

    if source.read(1):
        raise VaultOperationError(SOURCE_CHANGED_MESSAGE)

    return summary


def decrypt_chunk_stream(
    source: BinaryIO,
    destination: BinaryIO,
    master_key: bytes,
    *,
    vault_id: bytes,
    blob_id: bytes,
    plaintext_length: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    require_eof: bool = True,
) -> ChunkStreamSummary:
    """Authenticate and decrypt one bounded chunk stream."""
    if type(require_eof) is not bool:
        raise TypeError("require_eof must be a boolean")

    summary = describe_chunk_stream(
        plaintext_length,
        chunk_size=chunk_size,
    )

    try:
        for expected_index in range(summary.chunk_count):
            prefix = _read_encrypted_exact(
                source,
                CHUNK_RECORD_PREFIX.size,
            )
            (
                chunk_index,
                recorded_plaintext_length,
                nonce,
                ciphertext_length,
            ) = CHUNK_RECORD_PREFIX.unpack(prefix)

            expected_plaintext_length = _chunk_plaintext_length(
                summary,
                expected_index,
            )
            expected_ciphertext_length = expected_plaintext_length + AES_GCM_TAG_LENGTH

            if chunk_index != expected_index:
                raise ValueError("chunk index is out of order")

            if recorded_plaintext_length != expected_plaintext_length:
                raise ValueError("chunk plaintext length is invalid")

            if ciphertext_length != expected_ciphertext_length:
                raise ValueError("chunk ciphertext length is invalid")

            ciphertext = _read_encrypted_exact(
                source,
                ciphertext_length,
            )
            payload = EncryptedPayload(
                nonce=nonce,
                ciphertext=ciphertext,
            )
            associated_data = chunk_associated_data(
                vault_id,
                blob_id,
                plaintext_length=(summary.plaintext_length),
                chunk_size=(summary.chunk_size),
                chunk_count=(summary.chunk_count),
                chunk_index=(expected_index),
                chunk_plaintext_length=(expected_plaintext_length),
            )
            plaintext = decrypt_payload(
                payload,
                master_key,
                associated_data=(associated_data),
            )

            if len(plaintext) != expected_plaintext_length:
                raise ValueError("decrypted chunk length is invalid")

            _write_all(
                destination,
                plaintext,
            )

        if require_eof and source.read(1):
            raise ValueError("chunk stream contains trailing data")
    except (
        struct.error,
        TypeError,
        ValueError,
    ):
        raise VaultFormatError(INVALID_CHUNK_STREAM_MESSAGE) from None

    return summary


def chunk_associated_data(
    vault_id: bytes,
    blob_id: bytes,
    *,
    plaintext_length: int,
    chunk_size: int,
    chunk_count: int,
    chunk_index: int,
    chunk_plaintext_length: int,
) -> bytes:
    """Bind a chunk to its vault, blob, position, and layout."""
    _require_bytes_length(
        "vault_id",
        vault_id,
        VAULT_ID_LENGTH,
    )
    _require_bytes_length(
        "blob_id",
        blob_id,
        BLOB_ID_LENGTH,
    )
    _require_plaintext_length(plaintext_length)
    _require_chunk_size(chunk_size)

    expected_chunk_count = chunk_count_for_plaintext_length(
        plaintext_length,
        chunk_size=chunk_size,
    )

    if chunk_count != expected_chunk_count:
        raise ValueError("chunk_count does not match the plaintext length")

    if type(chunk_index) is not int:
        raise TypeError("chunk_index must be an integer")

    if not (0 <= chunk_index < chunk_count):
        raise ValueError("chunk_index is outside the chunk stream")

    expected_chunk_plaintext_length = _chunk_plaintext_length(
        describe_chunk_stream(
            plaintext_length,
            chunk_size=chunk_size,
        ),
        chunk_index,
    )

    if chunk_plaintext_length != expected_chunk_plaintext_length:
        raise ValueError("chunk_plaintext_length is invalid")

    return (
        CHUNK_STREAM_AAD_PREFIX
        + vault_id
        + blob_id
        + CHUNK_AAD_FIELDS.pack(
            plaintext_length,
            chunk_size,
            chunk_count,
            chunk_index,
            chunk_plaintext_length,
        )
    )


def _chunk_plaintext_length(
    summary: ChunkStreamSummary,
    chunk_index: int,
) -> int:
    if chunk_index < summary.chunk_count - 1:
        return summary.chunk_size

    if summary.plaintext_length == 0:
        return 0

    consumed = summary.chunk_size * (summary.chunk_count - 1)
    return summary.plaintext_length - consumed


def _read_source_exact(
    source: BinaryIO,
    length: int,
) -> bytes:
    chunks: list[bytes] = []
    remaining = length

    while remaining:
        chunk = source.read(remaining)

        if not chunk:
            raise VaultOperationError(SOURCE_CHANGED_MESSAGE)

        if len(chunk) > remaining:
            raise VaultOperationError(SOURCE_CHANGED_MESSAGE)

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def _read_encrypted_exact(
    source: BinaryIO,
    length: int,
) -> bytes:
    chunks: list[bytes] = []
    remaining = length

    while remaining:
        chunk = source.read(remaining)

        if not chunk or len(chunk) > remaining:
            raise VaultFormatError(INVALID_CHUNK_STREAM_MESSAGE)

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def _write_all(
    destination: BinaryIO,
    data: bytes,
) -> None:
    offset = 0

    while offset < len(data):
        remaining = len(data) - offset
        written = destination.write(data[offset:])

        if written is None or not 0 < written <= remaining:
            raise OSError("unable to write chunk stream")

        offset += written


def _require_plaintext_length(
    value: int,
) -> None:
    if type(value) is not int:
        raise TypeError("plaintext_length must be an integer")

    if not (0 <= value <= MAX_PLAINTEXT_LENGTH):
        raise ValueError("plaintext_length is outside the supported range")


def _require_chunk_size(
    value: int,
) -> None:
    if type(value) is not int:
        raise TypeError("chunk_size must be an integer")

    if not (1 <= value <= MAX_CHUNK_SIZE):
        raise ValueError("chunk_size is outside the supported range")


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(
        value,
        bytes,
    ):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
