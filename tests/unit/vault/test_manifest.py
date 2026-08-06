"""Tests for the file-bearing encrypted vault manifest."""

import json

import pytest

from usb_vault.core.errors import (
    EntryExistsError,
    EntryNotFoundError,
    VaultFormatError,
)
from usb_vault.core.storage.format import VAULT_ID_LENGTH
from usb_vault.core.vault.blob import BLOB_ID_LENGTH
from usb_vault.core.vault.manifest import (
    ENTRY_ID_LENGTH,
    MANIFEST_MAGIC,
    MANIFEST_VERSION,
    VaultEntry,
    VaultManifest,
    create_vault_entry,
    manifest_associated_data,
    normalize_entry_name,
)
from usb_vault.core.vault.blob import (
    MAX_BLOB_PLAINTEXT_LENGTH,
)


def _entry(
    name: str = "notes.txt",
    *,
    entry_byte: bytes = b"E",
    blob_byte: bytes = b"B",
    size: int = 12,
) -> VaultEntry:
    return VaultEntry(
        entry_id=(entry_byte * ENTRY_ID_LENGTH),
        blob_id=(blob_byte * BLOB_ID_LENGTH),
        name=name,
        size=size,
    )


def test_entry_size_can_exceed_legacy_blob_limit() -> None:
    entry = create_vault_entry(
        name="large.bin",
        size=(MAX_BLOB_PLAINTEXT_LENGTH + 1),
        blob_id=(b"B" * BLOB_ID_LENGTH),
        entry_id=(b"E" * ENTRY_ID_LENGTH),
    )

    assert entry.size == (MAX_BLOB_PLAINTEXT_LENGTH + 1)


def test_manifest_with_entries_round_trip() -> None:
    original = VaultManifest(
        entries=(
            _entry("notes.txt"),
            _entry(
                "photo.jpg",
                entry_byte=b"F",
                blob_byte=b"C",
                size=2_048,
            ),
        )
    )

    restored = VaultManifest.from_bytes(original.to_bytes())

    assert restored == original
    assert restored.entry_count == 2


def test_manifest_serialization_is_deterministic() -> None:
    first = VaultManifest(
        entries=(
            _entry("z.txt"),
            _entry(
                "a.txt",
                entry_byte=b"F",
                blob_byte=b"C",
            ),
        )
    )
    second = VaultManifest(entries=tuple(reversed(first.entries)))

    assert first.to_bytes() == second.to_bytes()


def test_manifest_contains_expected_version() -> None:
    payload = json.loads(VaultManifest().to_bytes())

    assert payload == {
        "entries": [],
        "magic": MANIFEST_MAGIC,
        "version": MANIFEST_VERSION,
    }


def test_legacy_empty_manifest_is_migrated() -> None:
    legacy = b'{"entries":[],"magic":"USBVAULTMANIFEST","version":1}'

    restored = VaultManifest.from_bytes(legacy)

    assert restored == VaultManifest()
    assert json.loads(restored.to_bytes())["version"] == MANIFEST_VERSION


def test_add_and_remove_entry() -> None:
    entry = _entry()
    manifest = VaultManifest().add_entry(entry)

    assert manifest.find_by_name("NOTES.TXT") == entry

    empty, removed = manifest.remove_entry("notes.txt")

    assert removed == entry
    assert empty.entry_count == 0


def test_duplicate_case_insensitive_name_is_rejected() -> None:
    manifest = VaultManifest(entries=(_entry("Notes.txt"),))

    with pytest.raises(EntryExistsError):
        manifest.add_entry(
            _entry(
                "notes.TXT",
                entry_byte=b"F",
                blob_byte=b"C",
            )
        )


def test_missing_entry_is_rejected() -> None:
    with pytest.raises(EntryNotFoundError):
        VaultManifest().remove_entry("missing.txt")


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        ".",
        "..",
        "folder/file.txt",
        "folder\\file.txt",
        "bad\x00name",
    ],
)
def test_unsafe_names_are_rejected(
    name: str,
) -> None:
    with pytest.raises(ValueError):
        normalize_entry_name(name)


def test_unicode_name_is_normalized() -> None:
    decomposed = "cafe\u0301.txt"

    entry = create_vault_entry(
        name=decomposed,
        size=0,
        blob_id=(b"B" * BLOB_ID_LENGTH),
    )

    assert entry.name == "café.txt"


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        (b'{"magic":"WRONG","version":2,"entries":[]}'),
        (b'{"magic":"USBVAULTMANIFEST","version":3,"entries":[]}'),
        (b'{"magic":"USBVAULTMANIFEST","version":2,"entries":{}}'),
        (b'{"magic":"USBVAULTMANIFEST","version":1,"entries":[{}]}'),
    ],
)
def test_invalid_manifests_are_rejected(
    payload: bytes,
) -> None:
    with pytest.raises(
        VaultFormatError,
        match=(r"^Invalid vault manifest\.$"),
    ):
        VaultManifest.from_bytes(payload)


def test_manifest_associated_data_binds_vault_id() -> None:
    first = manifest_associated_data(b"A" * VAULT_ID_LENGTH)
    second = manifest_associated_data(b"B" * VAULT_ID_LENGTH)

    assert first != second
