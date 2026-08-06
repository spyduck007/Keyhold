"""Version 3 vault container indexing and bounded payload copying."""

from __future__ import annotations

import os
import stat
import struct
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import BinaryIO

from usb_vault.core.crypto.encryption import (
    AES_GCM_TAG_LENGTH,
)
from usb_vault.core.crypto.payload_encryption import (
    EncryptedPayload,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
)
from usb_vault.core.errors import (
    VaultFormatError,
)
from usb_vault.core.storage.atomic_save import (
    atomic_write_file,
)
from usb_vault.core.storage.limits import (
    MAX_BLOB_COUNT,
    MAX_ENCRYPTED_MANIFEST_LENGTH,
    MAX_HEADER_LENGTH,
)
from usb_vault.core.storage.format import (
    VaultHeader,
)
from usb_vault.core.vault.chunk_stream import (
    BLOB_ID_LENGTH,
    MAX_PLAINTEXT_LENGTH,
    describe_chunk_stream,
)

STREAMING_CONTAINER_MAGIC = b"USBVLT03"
STREAMING_CONTAINER_PREFIX = struct.Struct(">8sIQI")
STREAMING_BLOB_PREFIX = struct.Struct(f">{BLOB_ID_LENGTH}sB3xQIQ")

MAX_BLOB_PAYLOAD_LENGTH = (1 << 63) - 1
COPY_BUFFER_SIZE = 1_048_576

INVALID_STREAMING_CONTAINER_MESSAGE = "Invalid vault container."


class BlobEncoding(IntEnum):
    """Encrypted blob encodings supported by container version 3."""

    SINGLE_PAYLOAD = 1
    CHUNK_STREAM = 2


@dataclass(
    frozen=True,
    slots=True,
)
class StoredBlob:
    """A bounded encrypted payload range stored in a regular file."""

    blob_id: bytes
    encoding: BlobEncoding
    plaintext_length: int
    chunk_size: int
    source_path: Path
    payload_offset: int
    payload_length: int

    def __post_init__(
        self,
    ) -> None:
        _require_bytes_length(
            "blob_id",
            self.blob_id,
            BLOB_ID_LENGTH,
        )

        if not isinstance(
            self.encoding,
            BlobEncoding,
        ):
            raise TypeError("encoding must be BlobEncoding")

        if type(self.plaintext_length) is not int:
            raise TypeError("plaintext_length must be an integer")

        if not (0 <= self.plaintext_length <= MAX_PLAINTEXT_LENGTH):
            raise ValueError("plaintext_length is outside the supported range")

        if type(self.chunk_size) is not int:
            raise TypeError("chunk_size must be an integer")

        if not isinstance(
            self.source_path,
            Path,
        ):
            raise TypeError("source_path must be Path")

        if type(self.payload_offset) is not int:
            raise TypeError("payload_offset must be an integer")

        if self.payload_offset < 0:
            raise ValueError("payload_offset must not be negative")

        if type(self.payload_length) is not int:
            raise TypeError("payload_length must be an integer")

        if not (0 <= self.payload_length <= MAX_BLOB_PAYLOAD_LENGTH):
            raise ValueError("payload_length is outside the supported range")

        if self.encoding is BlobEncoding.SINGLE_PAYLOAD:
            if self.chunk_size != 0:
                raise ValueError("single-payload blobs must use a zero chunk size")

            expected_payload_length = (
                AES_GCM_NONCE_LENGTH + self.plaintext_length + AES_GCM_TAG_LENGTH
            )

            if self.payload_length != expected_payload_length:
                raise ValueError("single-payload blob length is invalid")
        else:
            summary = describe_chunk_stream(
                self.plaintext_length,
                chunk_size=(self.chunk_size),
            )

            if self.payload_length != summary.serialized_length:
                raise ValueError("chunk-stream payload length is invalid")


@dataclass(
    frozen=True,
    slots=True,
)
class StreamingVaultIndex:
    """Version 3 metadata and on-disk encrypted blob locations."""

    path: Path
    header: VaultHeader
    encrypted_manifest: EncryptedPayload
    blobs: tuple[
        StoredBlob,
        ...,
    ] = ()

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.path,
            Path,
        ):
            raise TypeError("path must be Path")

        if not isinstance(
            self.header,
            VaultHeader,
        ):
            raise TypeError("header must be VaultHeader")

        if not isinstance(
            self.encrypted_manifest,
            EncryptedPayload,
        ):
            raise TypeError("encrypted_manifest must be EncryptedPayload")

        if not isinstance(
            self.blobs,
            tuple,
        ):
            raise TypeError("blobs must be a tuple")

        if not all(
            isinstance(
                blob,
                StoredBlob,
            )
            for blob in self.blobs
        ):
            raise TypeError("every blob must be StoredBlob")

        if len(self.blobs) > MAX_BLOB_COUNT:
            raise ValueError("vault contains too many blobs")

        blob_ids = [blob.blob_id for blob in self.blobs]

        if len(blob_ids) != len(set(blob_ids)):
            raise ValueError("blob identifiers must be unique")

    def find_blob(
        self,
        blob_id: bytes,
    ) -> StoredBlob | None:
        """Return the stored blob matching an identifier."""
        _require_bytes_length(
            "blob_id",
            blob_id,
            BLOB_ID_LENGTH,
        )

        for blob in self.blobs:
            if blob.blob_id == blob_id:
                return blob

        return None


def read_streaming_vault_index(
    path: str | Path,
) -> StreamingVaultIndex:
    """Index a version 3 vault without reading blob payloads."""
    vault_path = Path(path)
    file_descriptor = _open_regular_file(vault_path)

    try:
        with os.fdopen(
            file_descriptor,
            "rb",
        ) as source:
            file_descriptor = -1
            file_size = os.fstat(source.fileno()).st_size

            try:
                prefix = _read_exact(
                    source,
                    STREAMING_CONTAINER_PREFIX.size,
                )
                (
                    magic,
                    header_length,
                    manifest_ciphertext_length,
                    blob_count,
                ) = STREAMING_CONTAINER_PREFIX.unpack(prefix)

                if magic != STREAMING_CONTAINER_MAGIC:
                    raise ValueError("invalid container magic")

                _validate_container_lengths(
                    header_length=(header_length),
                    manifest_ciphertext_length=(manifest_ciphertext_length),
                    blob_count=blob_count,
                )

                header_bytes = _read_exact(
                    source,
                    header_length,
                )
                manifest_nonce = _read_exact(
                    source,
                    AES_GCM_NONCE_LENGTH,
                )
                manifest_ciphertext = _read_exact(
                    source,
                    manifest_ciphertext_length,
                )

                header = VaultHeader.from_bytes(header_bytes)
                encrypted_manifest = EncryptedPayload(
                    nonce=(manifest_nonce),
                    ciphertext=(manifest_ciphertext),
                )
                blobs: list[StoredBlob] = []

                for _ in range(blob_count):
                    blob_prefix = _read_exact(
                        source,
                        STREAMING_BLOB_PREFIX.size,
                    )
                    (
                        blob_id,
                        encoding_value,
                        plaintext_length,
                        chunk_size,
                        payload_length,
                    ) = STREAMING_BLOB_PREFIX.unpack(blob_prefix)

                    encoding = BlobEncoding(encoding_value)
                    payload_offset = source.tell()
                    payload_end = payload_offset + payload_length

                    if payload_end > file_size:
                        raise ValueError("blob payload is truncated")

                    blobs.append(
                        StoredBlob(
                            blob_id=blob_id,
                            encoding=encoding,
                            plaintext_length=(plaintext_length),
                            chunk_size=(chunk_size),
                            source_path=(vault_path),
                            payload_offset=(payload_offset),
                            payload_length=(payload_length),
                        )
                    )
                    source.seek(
                        payload_length,
                        os.SEEK_CUR,
                    )

                if source.tell() != file_size:
                    raise ValueError("container contains trailing data")
            except (
                OSError,
                struct.error,
                TypeError,
                ValueError,
                VaultFormatError,
            ):
                raise VaultFormatError(INVALID_STREAMING_CONTAINER_MESSAGE) from None
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)

    return StreamingVaultIndex(
        path=vault_path,
        header=header,
        encrypted_manifest=(encrypted_manifest),
        blobs=tuple(blobs),
    )


def write_streaming_vault(
    path: str | Path,
    *,
    header: VaultHeader,
    encrypted_manifest: EncryptedPayload,
    blobs: tuple[
        StoredBlob,
        ...,
    ] = (),
    overwrite: bool = False,
) -> None:
    """Atomically write V3 by copying bounded encrypted ranges."""
    index = StreamingVaultIndex(
        path=Path(path),
        header=header,
        encrypted_manifest=(encrypted_manifest),
        blobs=blobs,
    )
    header_bytes = index.header.to_bytes()
    manifest_ciphertext = index.encrypted_manifest.ciphertext

    _validate_container_lengths(
        header_length=(len(header_bytes)),
        manifest_ciphertext_length=(len(manifest_ciphertext)),
        blob_count=(len(index.blobs)),
    )

    ordered_blobs = tuple(
        sorted(
            index.blobs,
            key=lambda blob: blob.blob_id,
        )
    )

    def write_file(
        destination: BinaryIO,
    ) -> None:
        _write_all(
            destination,
            STREAMING_CONTAINER_PREFIX.pack(
                STREAMING_CONTAINER_MAGIC,
                len(header_bytes),
                len(manifest_ciphertext),
                len(ordered_blobs),
            ),
        )
        _write_all(
            destination,
            header_bytes,
        )
        _write_all(
            destination,
            index.encrypted_manifest.nonce,
        )
        _write_all(
            destination,
            manifest_ciphertext,
        )

        for blob in ordered_blobs:
            _write_all(
                destination,
                STREAMING_BLOB_PREFIX.pack(
                    blob.blob_id,
                    int(blob.encoding),
                    blob.plaintext_length,
                    blob.chunk_size,
                    blob.payload_length,
                ),
            )
            _copy_blob_payload(
                blob,
                destination,
            )

    atomic_write_file(
        index.path,
        write_file,
        overwrite=overwrite,
    )


def _copy_blob_payload(
    blob: StoredBlob,
    destination: BinaryIO,
) -> None:
    file_descriptor = _open_regular_file(blob.source_path)

    try:
        with os.fdopen(
            file_descriptor,
            "rb",
        ) as source:
            file_descriptor = -1
            file_size = os.fstat(source.fileno()).st_size
            payload_end = blob.payload_offset + blob.payload_length

            if payload_end > file_size:
                raise VaultFormatError(INVALID_STREAMING_CONTAINER_MESSAGE)

            source.seek(blob.payload_offset)
            remaining = blob.payload_length

            while remaining:
                chunk = source.read(
                    min(
                        COPY_BUFFER_SIZE,
                        remaining,
                    )
                )

                if not chunk:
                    raise VaultFormatError(INVALID_STREAMING_CONTAINER_MESSAGE)

                _write_all(
                    destination,
                    chunk,
                )
                remaining -= len(chunk)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


def _open_regular_file(
    path: Path,
) -> int:
    flags = os.O_RDONLY | getattr(
        os,
        "O_NOFOLLOW",
        0,
    )
    file_descriptor = os.open(
        path,
        flags,
    )

    try:
        file_status = os.fstat(file_descriptor)

        if not stat.S_ISREG(file_status.st_mode):
            raise VaultFormatError(INVALID_STREAMING_CONTAINER_MESSAGE)
    except Exception:
        os.close(file_descriptor)
        raise

    return file_descriptor


def _read_exact(
    source: BinaryIO,
    length: int,
) -> bytes:
    chunks: list[bytes] = []
    remaining = length

    while remaining:
        chunk = source.read(remaining)

        if not chunk or len(chunk) > remaining:
            raise ValueError("container is truncated")

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

        if written is None or not (0 < written <= remaining):
            raise OSError("unable to write vault container")

        offset += written


def _validate_container_lengths(
    *,
    header_length: int,
    manifest_ciphertext_length: int,
    blob_count: int,
) -> None:
    if header_length == 0 or header_length > MAX_HEADER_LENGTH:
        raise ValueError("invalid header length")

    if not (AES_GCM_TAG_LENGTH <= manifest_ciphertext_length <= MAX_ENCRYPTED_MANIFEST_LENGTH):
        raise ValueError("invalid encrypted manifest length")

    if blob_count > MAX_BLOB_COUNT:
        raise ValueError("invalid blob count")


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
