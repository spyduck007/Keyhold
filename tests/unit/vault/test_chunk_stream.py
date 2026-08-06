"""Tests for authenticated encrypted chunk streams."""

from __future__ import annotations

import io

import pytest

from usb_vault.core.crypto.encryption import (
    AES_GCM_TAG_LENGTH,
)
from usb_vault.core.errors import (
    UnlockError,
    VaultFormatError,
    VaultOperationError,
)
from usb_vault.core.vault.chunk_stream import (
    CHUNK_RECORD_PREFIX,
    DEFAULT_CHUNK_SIZE,
    describe_chunk_stream,
    decrypt_chunk_stream,
    encrypt_chunk_stream,
)

MASTER_KEY = b"M" * 32
OTHER_MASTER_KEY = b"N" * 32

VAULT_ID = b"V" * 16
OTHER_VAULT_ID = b"W" * 16

BLOB_ID = b"B" * 16
OTHER_BLOB_ID = b"C" * 16


@pytest.mark.parametrize(
    (
        "plaintext",
        "chunk_size",
        "expected_count",
    ),
    [
        (
            b"",
            4,
            1,
        ),
        (
            b"a",
            4,
            1,
        ),
        (
            b"abcd",
            4,
            1,
        ),
        (
            b"abcde",
            4,
            2,
        ),
        (
            b"abcdefgh",
            4,
            2,
        ),
        (
            b"abcdefghi",
            4,
            3,
        ),
    ],
)
def test_chunk_stream_round_trip(
    plaintext: bytes,
    chunk_size: int,
    expected_count: int,
) -> None:
    encrypted = io.BytesIO()

    summary = encrypt_chunk_stream(
        io.BytesIO(plaintext),
        encrypted,
        MASTER_KEY,
        vault_id=VAULT_ID,
        blob_id=BLOB_ID,
        plaintext_length=len(plaintext),
        chunk_size=chunk_size,
    )

    assert summary.chunk_count == expected_count
    assert len(encrypted.getvalue()) == summary.serialized_length

    decrypted = io.BytesIO()

    returned = decrypt_chunk_stream(
        io.BytesIO(encrypted.getvalue()),
        decrypted,
        MASTER_KEY,
        vault_id=VAULT_ID,
        blob_id=BLOB_ID,
        plaintext_length=len(plaintext),
        chunk_size=chunk_size,
    )

    assert returned == summary
    assert decrypted.getvalue() == plaintext


def test_default_chunk_size_is_one_mibibyte() -> None:
    assert DEFAULT_CHUNK_SIZE == 1_048_576


def test_summary_includes_record_and_tag_overhead() -> None:
    summary = describe_chunk_stream(
        9,
        chunk_size=4,
    )

    assert summary.chunk_count == 3
    assert summary.serialized_length == (9 + 3 * (CHUNK_RECORD_PREFIX.size + AES_GCM_TAG_LENGTH))


def test_ciphertext_tampering_is_rejected() -> None:
    encrypted = _encrypt(
        b"abcdefgh",
        chunk_size=4,
    )
    tampered = bytearray(encrypted)
    tampered[-1] ^= 1

    with pytest.raises(UnlockError):
        _decrypt(
            bytes(tampered),
            plaintext_length=8,
            chunk_size=4,
        )


@pytest.mark.parametrize(
    (
        "master_key",
        "vault_id",
        "blob_id",
    ),
    [
        (
            OTHER_MASTER_KEY,
            VAULT_ID,
            BLOB_ID,
        ),
        (
            MASTER_KEY,
            OTHER_VAULT_ID,
            BLOB_ID,
        ),
        (
            MASTER_KEY,
            VAULT_ID,
            OTHER_BLOB_ID,
        ),
    ],
)
def test_wrong_identity_or_key_is_rejected(
    master_key: bytes,
    vault_id: bytes,
    blob_id: bytes,
) -> None:
    encrypted = _encrypt(
        b"abcdefgh",
        chunk_size=4,
    )

    with pytest.raises(UnlockError):
        decrypt_chunk_stream(
            io.BytesIO(encrypted),
            io.BytesIO(),
            master_key,
            vault_id=vault_id,
            blob_id=blob_id,
            plaintext_length=8,
            chunk_size=4,
        )


def test_reordered_chunks_are_rejected_before_decryption() -> None:
    encrypted = _encrypt(
        b"abcdefgh",
        chunk_size=4,
    )
    record_length = CHUNK_RECORD_PREFIX.size + 4 + AES_GCM_TAG_LENGTH
    first = encrypted[:record_length]
    second = encrypted[record_length:]

    with pytest.raises(
        VaultFormatError,
        match=("Invalid encrypted chunk stream"),
    ):
        _decrypt(
            second + first,
            plaintext_length=8,
            chunk_size=4,
        )


def test_truncated_stream_is_rejected() -> None:
    encrypted = _encrypt(
        b"abcdefgh",
        chunk_size=4,
    )

    with pytest.raises(
        VaultFormatError,
        match=("Invalid encrypted chunk stream"),
    ):
        _decrypt(
            encrypted[:-1],
            plaintext_length=8,
            chunk_size=4,
        )


def test_trailing_data_is_rejected_by_default() -> None:
    encrypted = _encrypt(
        b"data",
        chunk_size=4,
    )

    with pytest.raises(
        VaultFormatError,
        match=("Invalid encrypted chunk stream"),
    ):
        _decrypt(
            encrypted + b"trailing",
            plaintext_length=4,
            chunk_size=4,
        )


def test_trailing_data_can_be_left_for_container_reader() -> None:
    encrypted = _encrypt(
        b"data",
        chunk_size=4,
    )
    source = io.BytesIO(encrypted + b"next-record")
    destination = io.BytesIO()

    decrypt_chunk_stream(
        source,
        destination,
        MASTER_KEY,
        vault_id=VAULT_ID,
        blob_id=BLOB_ID,
        plaintext_length=4,
        chunk_size=4,
        require_eof=False,
    )

    assert destination.getvalue() == b"data"
    assert source.read() == b"next-record"


@pytest.mark.parametrize(
    (
        "declared_length",
        "actual",
    ),
    [
        (
            5,
            b"four",
        ),
        (
            4,
            b"five!",
        ),
    ],
)
def test_source_length_changes_are_rejected(
    declared_length: int,
    actual: bytes,
) -> None:
    with pytest.raises(
        VaultOperationError,
        match=("Source file changed during encryption"),
    ):
        encrypt_chunk_stream(
            io.BytesIO(actual),
            io.BytesIO(),
            MASTER_KEY,
            vault_id=VAULT_ID,
            blob_id=BLOB_ID,
            plaintext_length=(declared_length),
            chunk_size=4,
        )


class TrackingReader(io.BytesIO):
    def __init__(
        self,
        data: bytes,
    ) -> None:
        super().__init__(data)
        self.largest_request = 0

    def read(
        self,
        size: int | None = -1,
        /,
    ) -> bytes:
        recorded_size = -1 if size is None else size
        self.largest_request = max(
            self.largest_request,
            recorded_size,
        )

        return super().read(size)

        return super().read(size)


def test_encryption_reads_at_most_one_plaintext_chunk() -> None:
    reader = TrackingReader(b"abcdefghij")

    encrypt_chunk_stream(
        reader,
        io.BytesIO(),
        MASTER_KEY,
        vault_id=VAULT_ID,
        blob_id=BLOB_ID,
        plaintext_length=10,
        chunk_size=4,
    )

    assert reader.largest_request <= 4


def test_invalid_chunk_size_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="chunk_size",
    ):
        describe_chunk_stream(
            10,
            chunk_size=0,
        )


def _encrypt(
    plaintext: bytes,
    *,
    chunk_size: int,
) -> bytes:
    destination = io.BytesIO()

    encrypt_chunk_stream(
        io.BytesIO(plaintext),
        destination,
        MASTER_KEY,
        vault_id=VAULT_ID,
        blob_id=BLOB_ID,
        plaintext_length=len(plaintext),
        chunk_size=chunk_size,
    )

    return destination.getvalue()


def _decrypt(
    ciphertext: bytes,
    *,
    plaintext_length: int,
    chunk_size: int,
) -> bytes:
    destination = io.BytesIO()

    decrypt_chunk_stream(
        io.BytesIO(ciphertext),
        destination,
        MASTER_KEY,
        vault_id=VAULT_ID,
        blob_id=BLOB_ID,
        plaintext_length=(plaintext_length),
        chunk_size=chunk_size,
    )

    return destination.getvalue()
