"""End-to-end tests for metadata-only vault entry renaming."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    VaultOperationError,
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
from usb_vault.core.vault.manifest import FOLDER_MARKER_NAME
from usb_vault.core.vault.operations import (
    add_file,
    create_folder,
    extract_file,
    list_files,
    move_folder,
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


def test_move_folder_relocates_every_nested_entry(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.txt"
    source.write_text("tax records", encoding="utf-8")

    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Documents",
    )
    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Archive",
    )
    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
        stored_name="Documents/2024.pdf",
    )
    before_blob_ids = {blob.blob_id for blob in read_vault_container(vault_path).blobs}

    moved = move_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Documents",
        destination_folder_path="Archive",
    )

    assert {entry.name for entry in moved} == {"Archive/Documents/2024.pdf"}

    entries = list_files(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
    )
    assert {entry.name for entry in entries} == {
        f"Archive/{FOLDER_MARKER_NAME}",
        f"Archive/Documents/{FOLDER_MARKER_NAME}",
        "Archive/Documents/2024.pdf",
    }

    # A move is metadata-only: every blob (including the moved file's
    # ciphertext) is left byte-for-byte untouched, proven here by identity
    # rather than content since three blobs now exist (two folder markers
    # plus the file).
    after_blob_ids = {blob.blob_id for blob in read_vault_container(vault_path).blobs}
    assert after_blob_ids == before_blob_ids


def test_move_folder_to_root_strips_the_parent_prefix(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Archive/Documents",
    )

    moved = move_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Archive/Documents",
        destination_folder_path="",
    )

    assert moved == ()
    entries = list_files(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
    )
    assert {entry.name for entry in entries} == {f"Documents/{FOLDER_MARKER_NAME}"}


def test_move_folder_into_itself_is_rejected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Documents",
    )
    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Documents/Taxes",
    )
    before = vault_path.read_bytes()

    with pytest.raises(VaultOperationError):
        move_folder(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            folder_path="Documents",
            destination_folder_path="Documents/Taxes",
        )

    assert vault_path.read_bytes() == before


def test_move_folder_collision_does_not_mutate_vault(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Archive/Documents",
    )
    create_folder(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        folder_path="Documents",
    )
    before = vault_path.read_bytes()

    with pytest.raises(EntryExistsError):
        move_folder(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            folder_path="Archive/Documents",
            destination_folder_path="",
        )

    assert vault_path.read_bytes() == before


def test_move_missing_folder_is_rejected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    with pytest.raises(EntryNotFoundError):
        move_folder(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            folder_path="Missing",
            destination_folder_path="",
        )
