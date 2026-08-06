"""Tests for the binary vault container."""

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
    VaultContainer,
)
from usb_vault.core.storage.format import (
    VAULT_ID_LENGTH,
    PasswordUsbKeySlot,
    VaultHeader,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def _container() -> VaultContainer:
    header = VaultHeader(
        vault_id=b"V" * VAULT_ID_LENGTH,
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=TEST_PARAMETERS,
        key_slots=(
            PasswordUsbKeySlot(
                key_id=b"K" * KEY_ID_LENGTH,
                wrapped_master_key=(
                    WrappedMasterKey(
                        nonce=(b"N" * AES_GCM_NONCE_LENGTH),
                        ciphertext=b"W" * 48,
                    )
                ),
            ),
        ),
    )

    return VaultContainer(
        header=header,
        encrypted_manifest=EncryptedPayload(
            nonce=(b"M" * AES_GCM_NONCE_LENGTH),
            ciphertext=b"C" * 32,
        ),
    )


def test_container_round_trip() -> None:
    original = _container()

    restored = VaultContainer.from_bytes(original.to_bytes())

    assert restored == original


def test_container_prefix_records_lengths() -> None:
    container = _container()
    serialized = container.to_bytes()

    (
        magic,
        header_length,
        ciphertext_length,
    ) = CONTAINER_PREFIX.unpack_from(serialized)

    assert magic == CONTAINER_MAGIC
    assert header_length == len(container.header.to_bytes())
    assert ciphertext_length == len(container.encrypted_manifest.ciphertext)


def test_trailing_data_is_rejected() -> None:
    serialized = _container().to_bytes() + b"extra"

    with pytest.raises(
        VaultFormatError,
        match=r"^Invalid vault container\.$",
    ):
        VaultContainer.from_bytes(serialized)


def test_invalid_magic_is_rejected() -> None:
    serialized = bytearray(_container().to_bytes())
    serialized[:8] = b"BADMAGIC"

    with pytest.raises(VaultFormatError):
        VaultContainer.from_bytes(bytes(serialized))


def test_impossible_lengths_are_rejected() -> None:
    serialized = bytearray(_container().to_bytes())
    struct.pack_into(
        ">I",
        serialized,
        8,
        0,
    )

    with pytest.raises(VaultFormatError):
        VaultContainer.from_bytes(bytes(serialized))
