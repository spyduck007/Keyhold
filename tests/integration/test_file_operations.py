"""End-to-end tests for encrypted file operations."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.password_kdf import Argon2Parameters
from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    UnlockError,
)
from usb_vault.core.storage.container import VaultContainer
from usb_vault.core.storage.reader import read_vault_container
from usb_vault.core.storage.writer import write_vault_container
from usb_vault.core.vault.creator import create_vault
from usb_vault.core.vault.operations import (
    add_file,
    delete_file,
    extract_file,
    list_files,
)
from usb_vault.core.vault.unlocker import unlock_vault

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

PASSWORD = "correct horse battery staple"


def _create_paths(
    tmp_path: Path,
) -> tuple[Path, Path]:
    vault_path = tmp_path / "PrivateVault.vault"
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


def test_add_list_extract_and_delete_file(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.txt"
    output = tmp_path / "output.txt"
    source.write_bytes(b"top secret school notes\n")

    added = add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
        stored_name="Notes.txt",
    )

    assert added.name == "Notes.txt"
    assert added.size == len(source.read_bytes())
    assert list_files(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
    ) == (added,)

    extracted = extract_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="notes.TXT",
        destination_path=output,
    )

    assert extracted == added
    assert output.read_bytes() == source.read_bytes()

    deleted = delete_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="NOTES.txt",
    )

    assert deleted == added
    assert (
        list_files(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
        )
        == ()
    )
    assert read_vault_container(vault_path).blobs == ()


def test_multiple_files_survive_atomic_updates(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"

    first.write_bytes(b"first")
    second.write_bytes(b"second")

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=second,
        stored_name="z.bin",
    )
    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=first,
        stored_name="a.bin",
    )

    entries = list_files(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
    )

    assert [entry.name for entry in entries] == [
        "a.bin",
        "z.bin",
    ]
    assert len(read_vault_container(vault_path).blobs) == 2


def test_duplicate_name_does_not_mutate_vault(
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
        stored_name="Duplicate.txt",
    )
    before = vault_path.read_bytes()

    with pytest.raises(EntryExistsError):
        add_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            source_path=second,
            stored_name="duplicate.TXT",
        )

    assert vault_path.read_bytes() == before


def test_wrong_password_cannot_mutate_vault(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.txt"
    source.write_text(
        "secret",
        encoding="utf-8",
    )
    before = vault_path.read_bytes()

    with pytest.raises(UnlockError):
        add_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password="wrong password",
            source_path=source,
        )

    assert vault_path.read_bytes() == before


def test_extract_refuses_existing_destination(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"

    source.write_text(
        "vault data",
        encoding="utf-8",
    )
    destination.write_text(
        "keep me",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
    )

    with pytest.raises(FileExistsError):
        extract_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            stored_name=source.name,
            destination_path=destination,
        )

    assert destination.read_text(encoding="utf-8") == "keep me"


def test_extract_can_explicitly_overwrite(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"

    source.write_text(
        "vault data",
        encoding="utf-8",
    )
    destination.write_text(
        "replace me",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
    )
    extract_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name=source.name,
        destination_path=destination,
        overwrite=True,
    )

    assert destination.read_text(encoding="utf-8") == "vault data"


def test_delete_missing_entry_is_rejected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    with pytest.raises(EntryNotFoundError):
        delete_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            stored_name="missing.txt",
        )


def test_blob_corruption_is_detected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.bin"
    source.write_bytes(b"secret binary data")

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
    )

    data = bytearray(vault_path.read_bytes())
    data[-1] ^= 0x01
    vault_path.write_bytes(data)

    with pytest.raises(UnlockError):
        extract_file(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
            stored_name=source.name,
            destination_path=(tmp_path / "out.bin"),
        )


def test_manifest_blob_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_paths(tmp_path)

    source = tmp_path / "source.txt"
    source.write_text(
        "secret",
        encoding="utf-8",
    )

    add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
    )

    container = read_vault_container(vault_path)

    write_vault_container(
        vault_path,
        VaultContainer(
            header=container.header,
            encrypted_manifest=(container.encrypted_manifest),
            blobs=(),
        ),
        overwrite=True,
    )

    with pytest.raises(UnlockError):
        unlock_vault(
            vault_path=vault_path,
            keyfile_path=keyfile_path,
            password=PASSWORD,
        )
