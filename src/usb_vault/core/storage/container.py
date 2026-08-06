"""Binary container for a vault header and encrypted manifest."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from usb_vault.core.crypto.encryption import AES_GCM_TAG_LENGTH
from usb_vault.core.crypto.payload_encryption import EncryptedPayload
from usb_vault.core.crypto.random import AES_GCM_NONCE_LENGTH
from usb_vault.core.errors import VaultFormatError
from usb_vault.core.storage.format import VaultHeader

CONTAINER_MAGIC = b"USBVLT01"
CONTAINER_PREFIX = struct.Struct(">8sIQ")
MAX_HEADER_LENGTH = 1_048_576
MAX_ENCRYPTED_MANIFEST_LENGTH = 16_777_216
INVALID_CONTAINER_MESSAGE = "Invalid vault container."


@dataclass(frozen=True, slots=True)
class VaultContainer:
    """The versioned vault header and encrypted manifest payload."""

    header: VaultHeader
    encrypted_manifest: EncryptedPayload

    def __post_init__(self) -> None:
        if not isinstance(self.header, VaultHeader):
            raise TypeError("header must be VaultHeader")

        if not isinstance(
            self.encrypted_manifest,
            EncryptedPayload,
        ):
            raise TypeError("encrypted_manifest must be EncryptedPayload")

    def to_bytes(self) -> bytes:
        """Serialize the container into its binary on-disk representation."""
        header_bytes = self.header.to_bytes()
        ciphertext = self.encrypted_manifest.ciphertext

        if len(header_bytes) > MAX_HEADER_LENGTH:
            raise ValueError("vault header is too large")

        if len(ciphertext) > MAX_ENCRYPTED_MANIFEST_LENGTH:
            raise ValueError("encrypted manifest is too large")

        prefix = CONTAINER_PREFIX.pack(
            CONTAINER_MAGIC,
            len(header_bytes),
            len(ciphertext),
        )

        return b"".join(
            (
                prefix,
                header_bytes,
                self.encrypted_manifest.nonce,
                ciphertext,
            )
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> VaultContainer:
        """Parse and strictly validate a serialized vault container."""
        try:
            if not isinstance(data, bytes):
                raise TypeError("data must be bytes")

            minimum_length = CONTAINER_PREFIX.size + AES_GCM_NONCE_LENGTH + AES_GCM_TAG_LENGTH

            if len(data) < minimum_length:
                raise ValueError("container is too short")

            (
                magic,
                header_length,
                ciphertext_length,
            ) = CONTAINER_PREFIX.unpack_from(data)

            if magic != CONTAINER_MAGIC:
                raise ValueError("invalid container magic")

            if header_length == 0 or header_length > MAX_HEADER_LENGTH:
                raise ValueError("invalid header length")

            if (
                ciphertext_length < AES_GCM_TAG_LENGTH
                or ciphertext_length > MAX_ENCRYPTED_MANIFEST_LENGTH
            ):
                raise ValueError("invalid encrypted manifest length")

            expected_length = (
                CONTAINER_PREFIX.size + header_length + AES_GCM_NONCE_LENGTH + ciphertext_length
            )

            if len(data) != expected_length:
                raise ValueError("container length does not match its prefix")

            header_start = CONTAINER_PREFIX.size
            header_end = header_start + header_length
            nonce_end = header_end + AES_GCM_NONCE_LENGTH

            header = VaultHeader.from_bytes(data[header_start:header_end])
            encrypted_manifest = EncryptedPayload(
                nonce=data[header_end:nonce_end],
                ciphertext=data[nonce_end:],
            )

            return cls(
                header=header,
                encrypted_manifest=encrypted_manifest,
            )
        except (
            struct.error,
            TypeError,
            ValueError,
            VaultFormatError,
        ):
            raise VaultFormatError(INVALID_CONTAINER_MESSAGE) from None
