"""End-to-end tests for metadata-only vault entry renaming."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
)
from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.storage.streaming_container import (
    StoredBlob,
)
from usb_vault.core.vault.creator import (
    create_vault,
)
from usb_vault.core.vault.operations import (
    add_file,
    extract_file,
    list_files,
    rename_file,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

PASSWORD = "correct horse battery staple"


def _create_paths(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
]:
    vault_path = tmp_path / "Private.vault"
    keyfile_path = tmp_path / ".authkey"

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )

    return (
        vault_path,
        keyfile_path,
    )


def _stored_payload(
    vault_path: Path,
) -> tuple[
    bytes,
    bytes,
]:
    container = read_vault_container(vault_path)

    assert len(container.blobs) == 1

    blob = container.blobs[0]
    assert isinstance(
        blob,
        StoredBlob,
    )

    with blob.source_path.open("rb") as source:
        source.seek(blob.payload_offset)
        payload = source.read(blob.payload_length)

    return (
        blob.blob_id,
        payload,
    )


def test_rename_preserves_encrypted_blob(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source_path = tmp_path / "source.bin"
    output_path = tmp_path / "output.bin"
    source_path.write_bytes(b"encrypted payload must remain unchanged")

    added = add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source_path,
        stored_name="Original.bin",
    )
    before_blob_id, before_payload = _stored_payload(vault_path)

    renamed = rename_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="original.BIN",
        new_name="Renamed.bin",
    )

    assert renamed.name == "Renamed.bin"
    assert renamed.size == added.size
    assert list_files(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
    ) == (renamed,)

    after_blob_id, after_payload = _stored_payload(vault_path)

    assert after_blob_id == before_blob_id
    assert after_payload == before_payload

    with pytest.raises(EntryNotFoundError):
        extract_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            stored_name="Original.bin",
            destination_path=output_path,
        )

    extract_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="Renamed.bin",
        destination_path=output_path,
    )

    assert output_path.read_bytes() == source_path.read_bytes()


def test_case_only_rename_is_allowed(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source_path = tmp_path / "notes.txt"
    source_path.write_text(
        "case-only rename",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source_path,
        stored_name="Notes.txt",
    )

    renamed = rename_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="Notes.txt",
        new_name="notes.txt",
    )

    assert renamed.name == "notes.txt"


def test_rename_collision_does_not_mutate_vault(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"

    first.write_text(
        "first",
        encoding="utf-8",
    )
    second.write_text(
        "second",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=first,
        stored_name="First.txt",
    )
    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=second,
        stored_name="Second.txt",
    )

    before = vault_path.read_bytes()

    with pytest.raises(EntryExistsError):
        rename_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            stored_name="First.txt",
            new_name="second.TXT",
        )

    assert vault_path.read_bytes() == before
