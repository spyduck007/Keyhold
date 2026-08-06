"""Legacy in-memory vault containers and unified blob metadata."""

from __future__ import annotations

import struct
from dataclasses import dataclass

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
from usb_vault.core.storage.format import (
    VaultHeader,
)
from usb_vault.core.storage.limits import (
    MAX_BLOB_COUNT,
    MAX_ENCRYPTED_MANIFEST_LENGTH,
    MAX_HEADER_LENGTH,
)
from usb_vault.core.storage.streaming_container import (
    StoredBlob,
)
from usb_vault.core.vault.blob import (
    BLOB_ID_LENGTH,
    MAX_BLOB_CIPHERTEXT_LENGTH,
    EncryptedBlob,
)

LEGACY_CONTAINER_MAGIC = b"USBVLT01"
CONTAINER_MAGIC = b"USBVLT02"

LEGACY_CONTAINER_PREFIX = struct.Struct(">8sIQ")
CONTAINER_PREFIX = struct.Struct(">8sIQI")
BLOB_PREFIX = struct.Struct(f">{BLOB_ID_LENGTH}sQ")

INVALID_CONTAINER_MESSAGE = "Invalid vault container."

VaultBlob = EncryptedBlob | StoredBlob


@dataclass(frozen=True, slots=True)
class VaultContainer:
    """Parsed vault metadata and encrypted blob records."""

    header: VaultHeader
    encrypted_manifest: EncryptedPayload
    blobs: tuple[VaultBlob, ...] = ()
    storage_version: int = 2

    def __post_init__(self) -> None:
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
                (
                    EncryptedBlob,
                    StoredBlob,
                ),
            )
            for blob in self.blobs
        ):
            raise TypeError("every blob must be EncryptedBlob or StoredBlob")

        if type(self.storage_version) is not int:
            raise TypeError("storage_version must be an integer")

        if self.storage_version not in (
            1,
            2,
            3,
        ):
            raise ValueError("unsupported storage version")

        if len(self.blobs) > MAX_BLOB_COUNT:
            raise ValueError("vault contains too many blobs")

        blob_ids = [blob.blob_id for blob in self.blobs]

        if len(blob_ids) != len(set(blob_ids)):
            raise ValueError("blob identifiers must be unique")

        if self.storage_version == 3:
            if not all(
                isinstance(
                    blob,
                    StoredBlob,
                )
                for blob in self.blobs
            ):
                raise ValueError("version 3 containers require stored blob records")
        elif any(
            isinstance(
                blob,
                StoredBlob,
            )
            for blob in self.blobs
        ):
            raise ValueError("legacy containers cannot contain stored blob records")

    def to_bytes(self) -> bytes:
        """Serialize the version 2 in-memory container format."""
        if self.storage_version == 3:
            raise ValueError("version 3 containers must be written with the streaming writer")

        legacy_blobs: list[EncryptedBlob] = []

        for blob in self.blobs:
            if not isinstance(
                blob,
                EncryptedBlob,
            ):
                raise ValueError("legacy serialization requires in-memory encrypted blobs")

            legacy_blobs.append(blob)

        header_bytes = self.header.to_bytes()
        manifest_ciphertext = self.encrypted_manifest.ciphertext

        if len(header_bytes) > MAX_HEADER_LENGTH:
            raise ValueError("vault header is too large")

        if len(manifest_ciphertext) > MAX_ENCRYPTED_MANIFEST_LENGTH:
            raise ValueError("encrypted manifest is too large")

        ordered_blobs = sorted(
            legacy_blobs,
            key=lambda blob: blob.blob_id,
        )

        parts: list[bytes] = [
            CONTAINER_PREFIX.pack(
                CONTAINER_MAGIC,
                len(header_bytes),
                len(manifest_ciphertext),
                len(ordered_blobs),
            ),
            header_bytes,
            self.encrypted_manifest.nonce,
            manifest_ciphertext,
        ]

        for blob in ordered_blobs:
            ciphertext = blob.payload.ciphertext

            parts.extend(
                (
                    BLOB_PREFIX.pack(
                        blob.blob_id,
                        len(ciphertext),
                    ),
                    blob.payload.nonce,
                    ciphertext,
                )
            )

        return b"".join(parts)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
    ) -> VaultContainer:
        """Parse version 1 and version 2 containers."""
        try:
            if not isinstance(
                data,
                bytes,
            ):
                raise TypeError("data must be bytes")

            if len(data) < 8:
                raise ValueError("container is too short")

            magic = data[:8]

            if magic == LEGACY_CONTAINER_MAGIC:
                return cls._from_legacy_bytes(data)

            if magic != CONTAINER_MAGIC:
                raise ValueError("invalid container magic")

            return cls._from_current_bytes(data)
        except (
            struct.error,
            TypeError,
            ValueError,
            VaultFormatError,
        ):
            raise VaultFormatError(INVALID_CONTAINER_MESSAGE) from None

    @classmethod
    def _from_current_bytes(
        cls,
        data: bytes,
    ) -> VaultContainer:
        minimum_length = CONTAINER_PREFIX.size + AES_GCM_NONCE_LENGTH + AES_GCM_TAG_LENGTH

        if len(data) < minimum_length:
            raise ValueError("container is too short")

        (
            magic,
            header_length,
            manifest_ciphertext_length,
            blob_count,
        ) = CONTAINER_PREFIX.unpack_from(data)

        if magic != CONTAINER_MAGIC:
            raise ValueError("invalid container magic")

        _validate_lengths(
            header_length=header_length,
            manifest_ciphertext_length=(manifest_ciphertext_length),
            blob_count=blob_count,
        )

        offset = CONTAINER_PREFIX.size
        header_end = offset + header_length
        manifest_nonce_end = header_end + AES_GCM_NONCE_LENGTH
        manifest_ciphertext_end = manifest_nonce_end + manifest_ciphertext_length

        if manifest_ciphertext_end > len(data):
            raise ValueError("container is truncated")

        header = VaultHeader.from_bytes(data[offset:header_end])

        encrypted_manifest = EncryptedPayload(
            nonce=data[header_end:manifest_nonce_end],
            ciphertext=data[manifest_nonce_end:manifest_ciphertext_end],
        )

        offset = manifest_ciphertext_end
        blobs: list[EncryptedBlob] = []

        for _ in range(blob_count):
            prefix_end = offset + BLOB_PREFIX.size

            if prefix_end > len(data):
                raise ValueError("blob prefix is truncated")

            (
                blob_id,
                ciphertext_length,
            ) = BLOB_PREFIX.unpack_from(
                data,
                offset,
            )

            if not (AES_GCM_TAG_LENGTH <= ciphertext_length <= MAX_BLOB_CIPHERTEXT_LENGTH):
                raise ValueError("invalid blob ciphertext length")

            nonce_start = prefix_end
            nonce_end = nonce_start + AES_GCM_NONCE_LENGTH
            ciphertext_end = nonce_end + ciphertext_length

            if ciphertext_end > len(data):
                raise ValueError("blob is truncated")

            blobs.append(
                EncryptedBlob(
                    blob_id=blob_id,
                    payload=EncryptedPayload(
                        nonce=data[nonce_start:nonce_end],
                        ciphertext=data[nonce_end:ciphertext_end],
                    ),
                )
            )

            offset = ciphertext_end

        if offset != len(data):
            raise ValueError("container contains trailing data")

        return cls(
            header=header,
            encrypted_manifest=(encrypted_manifest),
            blobs=tuple(blobs),
            storage_version=2,
        )

    @classmethod
    def _from_legacy_bytes(
        cls,
        data: bytes,
    ) -> VaultContainer:
        minimum_length = LEGACY_CONTAINER_PREFIX.size + AES_GCM_NONCE_LENGTH + AES_GCM_TAG_LENGTH

        if len(data) < minimum_length:
            raise ValueError("legacy container is too short")

        (
            magic,
            header_length,
            ciphertext_length,
        ) = LEGACY_CONTAINER_PREFIX.unpack_from(data)

        if magic != LEGACY_CONTAINER_MAGIC:
            raise ValueError("invalid legacy container magic")

        _validate_lengths(
            header_length=header_length,
            manifest_ciphertext_length=(ciphertext_length),
            blob_count=0,
        )

        expected_length = (
            LEGACY_CONTAINER_PREFIX.size + header_length + AES_GCM_NONCE_LENGTH + ciphertext_length
        )

        if len(data) != expected_length:
            raise ValueError("legacy container length is invalid")

        header_start = LEGACY_CONTAINER_PREFIX.size
        header_end = header_start + header_length
        nonce_end = header_end + AES_GCM_NONCE_LENGTH

        return cls(
            header=VaultHeader.from_bytes(data[header_start:header_end]),
            encrypted_manifest=(
                EncryptedPayload(
                    nonce=data[header_end:nonce_end],
                    ciphertext=data[nonce_end:],
                )
            ),
            storage_version=1,
        )

    def find_blob(
        self,
        blob_id: bytes,
    ) -> VaultBlob | None:
        """Return the encrypted blob matching an identifier."""
        if not isinstance(
            blob_id,
            bytes,
        ):
            raise TypeError("blob_id must be bytes")

        if len(blob_id) != BLOB_ID_LENGTH:
            raise ValueError(f"blob_id must be exactly {BLOB_ID_LENGTH} bytes")

        for blob in self.blobs:
            if blob.blob_id == blob_id:
                return blob

        return None


def _validate_lengths(
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
