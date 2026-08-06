"""Tests for version 2 and legacy vault containers."""

import struct

import pytest

from usb_vault.core.crypto.encryption import WrappedMasterKey
from usb_vault.core.crypto.password_kdf import Argon2Parameters
from usb_vault.core.crypto.payload_encryption import EncryptedPayload
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    ARGON2_SALT_LENGTH,
)
from usb_vault.core.errors import VaultFormatError
from usb_vault.core.keys.keyfile import KEY_ID_LENGTH
from usb_vault.core.storage.container import (
    CONTAINER_MAGIC,
    CONTAINER_PREFIX,
    LEGACY_CONTAINER_MAGIC,
    LEGACY_CONTAINER_PREFIX,
    VaultContainer,
)
from usb_vault.core.storage.format import (
    VAULT_ID_LENGTH,
    PasswordUsbKeySlot,
    VaultHeader,
)
from usb_vault.core.vault.blob import (
    BLOB_ID_LENGTH,
    EncryptedBlob,
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
        ciphertext=b"C" * 32,
    )


def _blob() -> EncryptedBlob:
    return EncryptedBlob(
        blob_id=(b"B" * BLOB_ID_LENGTH),
        payload=EncryptedPayload(
            nonce=(b"Q" * AES_GCM_NONCE_LENGTH),
            ciphertext=b"D" * 48,
        ),
    )


def test_current_container_round_trip_with_blob() -> None:
    original = VaultContainer(
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
        blobs=(_blob(),),
    )

    restored = VaultContainer.from_bytes(original.to_bytes())

    assert restored == original
    assert restored.find_blob(b"B" * BLOB_ID_LENGTH) == _blob()


def test_current_prefix_records_blob_count() -> None:
    serialized = VaultContainer(
        header=_header(),
        encrypted_manifest=(_manifest_payload()),
        blobs=(_blob(),),
    ).to_bytes()

    (
        magic,
        _,
        _,
        blob_count,
    ) = CONTAINER_PREFIX.unpack_from(serialized)

    assert magic == CONTAINER_MAGIC
    assert blob_count == 1


def test_legacy_container_is_still_readable() -> None:
    header_bytes = _header().to_bytes()
    payload = _manifest_payload()

    serialized = b"".join(
        (
            LEGACY_CONTAINER_PREFIX.pack(
                LEGACY_CONTAINER_MAGIC,
                len(header_bytes),
                len(payload.ciphertext),
            ),
            header_bytes,
            payload.nonce,
            payload.ciphertext,
        )
    )

    restored = VaultContainer.from_bytes(serialized)

    assert restored.header == _header()
    assert restored.encrypted_manifest == payload
    assert restored.blobs == ()


def test_duplicate_blob_ids_are_rejected() -> None:
    blob = _blob()

    with pytest.raises(
        ValueError,
        match=("identifiers must be unique"),
    ):
        VaultContainer(
            header=_header(),
            encrypted_manifest=(_manifest_payload()),
            blobs=(blob, blob),
        )


def test_trailing_data_is_rejected() -> None:
    serialized = (
        VaultContainer(
            header=_header(),
            encrypted_manifest=(_manifest_payload()),
        ).to_bytes()
        + b"extra"
    )

    with pytest.raises(VaultFormatError):
        VaultContainer.from_bytes(serialized)


def test_impossible_blob_count_is_rejected() -> None:
    serialized = bytearray(
        VaultContainer(
            header=_header(),
            encrypted_manifest=(_manifest_payload()),
        ).to_bytes()
    )

    struct.pack_into(
        ">I",
        serialized,
        CONTAINER_PREFIX.size - 4,
        10_001,
    )

    with pytest.raises(VaultFormatError):
        VaultContainer.from_bytes(bytes(serialized))
