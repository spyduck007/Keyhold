"""Tests for the persistent non-secret vault registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from usb_vault.ui.vault_library import (
    LIBRARY_MAGIC,
    LIBRARY_PATH_ENVIRONMENT_VARIABLE,
    LIBRARY_VERSION,
    VaultLibraryFormatError,
    VaultLibraryStore,
    default_vault_library_path,
)

VAULT_ID_A = b"A" * 16
VAULT_ID_B = b"B" * 16
OPENED_AT = datetime(
    2026,
    8,
    6,
    21,
    0,
    tzinfo=UTC,
)


@dataclass
class FakeVaultIdentityReader:
    """Return configured public vault identities."""

    identities: dict[
        Path,
        bytes,
    ]

    def read_vault_id(
        self,
        vault_path: Path,
    ) -> bytes:
        return self.identities[vault_path]


def _clock() -> datetime:
    return OPENED_AT


def test_register_persists_only_non_secret_metadata(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"placeholder")

    reader = FakeVaultIdentityReader(
        {
            vault_path: VAULT_ID_A,
        }
    )
    store = VaultLibraryStore(
        library_path,
        identity_reader=reader,
        clock=_clock,
    )

    entry = store.register_vault(vault_path)

    assert entry.vault_id == VAULT_ID_A
    assert entry.display_name == "Private"
    assert entry.is_available

    raw_text = library_path.read_text(encoding="utf-8")
    payload: object = json.loads(raw_text)

    assert payload == {
        "magic": LIBRARY_MAGIC,
        "version": LIBRARY_VERSION,
        "vaults": [
            {
                "display_name": ("Private"),
                "last_opened_at": ("2026-08-06T21:00:00Z"),
                "vault_id": (VAULT_ID_A.hex()),
                "vault_path": str(vault_path),
            }
        ],
    }

    lowered = raw_text.lower()

    assert "password" not in lowered
    assert "recovery" not in lowered
    assert "keyfile" not in lowered
    assert "secret" not in lowered


def test_library_survives_store_restart(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    vault_path = tmp_path / "Private.vault"
    reader = FakeVaultIdentityReader(
        {
            vault_path: VAULT_ID_A,
        }
    )

    first_store = VaultLibraryStore(
        library_path,
        identity_reader=reader,
        clock=_clock,
    )
    first_store.register_vault(
        vault_path,
        display_name="School Files",
    )

    second_store = VaultLibraryStore(
        library_path,
        identity_reader=reader,
        clock=_clock,
    )

    entries = second_store.list_entries()

    assert len(entries) == 1
    assert entries[0].vault_id == VAULT_ID_A
    assert entries[0].display_name == "School Files"
    assert entries[0].vault_path == vault_path


def test_same_vault_at_new_path_updates_one_record(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    old_path = tmp_path / "Old.vault"
    new_path = tmp_path / "Moved.vault"
    reader = FakeVaultIdentityReader(
        {
            old_path: VAULT_ID_A,
            new_path: VAULT_ID_A,
        }
    )
    store = VaultLibraryStore(
        library_path,
        identity_reader=reader,
        clock=_clock,
    )

    store.register_vault(
        old_path,
        display_name="My Vault",
    )
    updated = store.register_vault(new_path)

    entries = store.list_entries()

    assert len(entries) == 1
    assert updated.vault_path == new_path
    assert updated.display_name == "My Vault"


def test_different_vault_replacing_same_path_removes_stale_record(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    vault_path = tmp_path / "Private.vault"
    identities = {
        vault_path: VAULT_ID_A,
    }
    reader = FakeVaultIdentityReader(identities)
    store = VaultLibraryStore(
        library_path,
        identity_reader=reader,
        clock=_clock,
    )

    store.register_vault(vault_path)

    identities[vault_path] = VAULT_ID_B
    store.register_vault(vault_path)

    entries = store.list_entries()

    assert len(entries) == 1
    assert entries[0].vault_id == VAULT_ID_B


def test_rename_and_remove_do_not_touch_vault_file(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"encrypted vault bytes")

    store = VaultLibraryStore(
        library_path,
        identity_reader=(
            FakeVaultIdentityReader(
                {
                    vault_path: (VAULT_ID_A),
                }
            )
        ),
        clock=_clock,
    )
    store.register_vault(vault_path)

    renamed = store.rename_vault(
        VAULT_ID_A,
        "Renamed Card",
    )

    assert renamed.display_name == "Renamed Card"
    assert vault_path.read_bytes() == b"encrypted vault bytes"

    assert store.remove_vault(VAULT_ID_A)
    assert store.list_entries() == ()
    assert vault_path.read_bytes() == b"encrypted vault bytes"


def test_availability_is_calculated_from_current_filesystem(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    vault_path = tmp_path / "Private.vault"
    vault_path.write_bytes(b"placeholder")

    store = VaultLibraryStore(
        library_path,
        identity_reader=(
            FakeVaultIdentityReader(
                {
                    vault_path: (VAULT_ID_A),
                }
            )
        ),
        clock=_clock,
    )
    registered = store.register_vault(vault_path)

    assert registered.is_available

    vault_path.unlink()

    assert not registered.is_available


def test_invalid_library_is_rejected(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "vault-library.json"
    library_path.write_text(
        '{"version":999}',
        encoding="utf-8",
    )

    store = VaultLibraryStore(library_path)

    with pytest.raises(
        VaultLibraryFormatError,
        match="Invalid vault library",
    ):
        store.list_entries()


def test_default_path_can_be_overridden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_path = tmp_path / "custom.json"
    monkeypatch.setenv(
        LIBRARY_PATH_ENVIRONMENT_VARIABLE,
        str(custom_path),
    )

    assert default_vault_library_path() == custom_path
