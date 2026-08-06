"""End-to-end tests for the version 3 streaming runtime."""

from pathlib import Path

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.crypto.payload_encryption import (
    encrypt_payload,
)
from usb_vault.core.storage.container import (
    CONTAINER_MAGIC,
    VaultContainer,
)
from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.storage.streaming_container import (
    STREAMING_CONTAINER_MAGIC,
    BlobEncoding,
    StoredBlob,
)
from usb_vault.core.storage.writer import (
    write_vault_container,
)
from usb_vault.core.vault.blob import (
    encrypt_blob,
)
from usb_vault.core.vault.creator import (
    create_vault,
)
from usb_vault.core.vault.manifest import (
    ENTRY_ID_LENGTH,
    create_vault_entry,
    manifest_associated_data,
)
from usb_vault.core.vault.operations import (
    add_file,
    delete_file,
    extract_file,
)
from usb_vault.core.vault.unlocker import (
    unlock_vault,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

PASSWORD = "correct horse battery staple"


def _create_vault(
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


def test_new_vault_uses_version_three(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        _,
    ) = _create_vault(tmp_path)

    assert vault_path.read_bytes()[:8] == STREAMING_CONTAINER_MAGIC

    container = read_vault_container(vault_path)

    assert container.storage_version == 3
    assert container.blobs == ()


def test_file_round_trip_uses_chunk_stream(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_vault(tmp_path)

    source = tmp_path / "source.bin"
    destination = tmp_path / "restored.bin"
    block = bytes(range(256)) * 4096

    with source.open("wb") as output:
        output.write(block)
        output.write(block)
        output.write(block)
        output.write(b"final bytes")

    added = add_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        source_path=source,
    )

    container = read_vault_container(vault_path)

    assert container.storage_version == 3
    assert len(container.blobs) == 1

    blob = container.blobs[0]

    assert isinstance(
        blob,
        StoredBlob,
    )
    assert blob.encoding is BlobEncoding.CHUNK_STREAM
    assert blob.plaintext_length == added.size

    extracted = extract_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name=source.name,
        destination_path=destination,
    )

    assert extracted == added
    assert destination.read_bytes() == source.read_bytes()


def test_legacy_v2_blob_can_be_read_and_is_migrated(
    tmp_path: Path,
) -> None:
    (
        vault_path,
        keyfile_path,
    ) = _create_vault(tmp_path)

    initial = read_vault_container(vault_path)

    write_vault_container(
        vault_path,
        VaultContainer(
            header=initial.header,
            encrypted_manifest=(initial.encrypted_manifest),
            storage_version=2,
        ),
        overwrite=True,
    )

    assert vault_path.read_bytes()[:8] == CONTAINER_MAGIC

    plaintext = b"legacy encrypted data"

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
    ) as session:
        master_key = session.copy_master_key()
        blob = encrypt_blob(
            plaintext,
            master_key,
            vault_id=(session.header.vault_id),
        )
        entry = create_vault_entry(
            name="legacy.txt",
            size=len(plaintext),
            blob_id=blob.blob_id,
            entry_id=(b"E" * ENTRY_ID_LENGTH),
        )
        manifest = session.manifest.add_entry(entry)
        encrypted_manifest = encrypt_payload(
            manifest.to_bytes(),
            master_key,
            associated_data=(manifest_associated_data(session.header.vault_id)),
        )

        write_vault_container(
            vault_path,
            VaultContainer(
                header=session.header,
                encrypted_manifest=(encrypted_manifest),
                blobs=(blob,),
                storage_version=2,
            ),
            overwrite=True,
        )

    destination = tmp_path / "legacy-output.txt"

    extract_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="legacy.txt",
        destination_path=destination,
    )

    assert destination.read_bytes() == plaintext

    delete_file(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        stored_name="legacy.txt",
    )

    assert vault_path.read_bytes()[:8] == STREAMING_CONTAINER_MAGIC
    assert read_vault_container(vault_path).storage_version == 3
