"""Tests for supported vault-header formats."""

import json
from collections.abc import Callable
from typing import Any

import pytest

from usb_vault.core.crypto.encryption import (
    WrappedMasterKey,
)
from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    ARGON2_SALT_LENGTH,
)
from usb_vault.core.errors import (
    VaultFormatError,
)
from usb_vault.core.keys.keyfile import (
    KEY_ID_LENGTH,
)
from usb_vault.core.keys.recovery import (
    RECOVERY_ID_LENGTH,
)
from usb_vault.core.storage.format import (
    LEGACY_VAULT_FORMAT_VERSION,
    VAULT_CIPHER_IDENTIFIER,
    VAULT_FORMAT_VERSION,
    VAULT_ID_LENGTH,
    PasswordUsbKeySlot,
    RecoveryKeySlot,
    VaultHeader,
    create_initial_vault_header,
)

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)

Mutation = Callable[
    [dict[str, Any]],
    None,
]


def _wrapped_master_key(
    fill: bytes = b"C",
) -> WrappedMasterKey:
    return WrappedMasterKey(
        nonce=(b"N" * AES_GCM_NONCE_LENGTH),
        ciphertext=fill * 48,
    )


def _usb_slot() -> PasswordUsbKeySlot:
    return PasswordUsbKeySlot(
        key_id=(b"K" * KEY_ID_LENGTH),
        wrapped_master_key=(_wrapped_master_key()),
    )


def _recovery_slot() -> RecoveryKeySlot:
    return RecoveryKeySlot(
        recovery_id=(b"R" * RECOVERY_ID_LENGTH),
        wrapped_master_key=(_wrapped_master_key(b"D")),
    )


def _header(
    *,
    recovery: bool = False,
    version: int = VAULT_FORMAT_VERSION,
) -> VaultHeader:
    return VaultHeader(
        vault_id=(b"V" * VAULT_ID_LENGTH),
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=(TEST_PARAMETERS),
        key_slots=(_usb_slot(),),
        recovery_slots=((_recovery_slot(),) if recovery else ()),
        version=version,
    )


def test_current_vault_header_round_trip() -> None:
    original = _header(recovery=True)

    restored = VaultHeader.from_bytes(original.to_bytes())

    assert restored == original


def test_legacy_vault_header_round_trip() -> None:
    original = _header(version=(LEGACY_VAULT_FORMAT_VERSION))

    restored = VaultHeader.from_bytes(original.to_bytes())

    assert restored == original
    assert restored.recovery_slots == ()


def test_vault_header_serialization_is_deterministic() -> None:
    header = _header(recovery=True)

    assert header.to_bytes() == header.to_bytes()


def test_serialized_header_contains_versioned_algorithms() -> None:
    payload = json.loads(_header(recovery=True).to_bytes())

    assert payload["magic"] == "USBVAULT"
    assert payload["version"] == VAULT_FORMAT_VERSION
    assert payload["kdf"]["name"] == "argon2id"
    assert payload["vault_cipher"] == VAULT_CIPHER_IDENTIFIER
    assert payload["key_slots"][0]["wrap_cipher"] == "aes-256-gcm"
    assert payload["recovery_slots"][0]["slot_type"] == "password_recovery"


def test_create_initial_header_uses_current_version() -> None:
    header = create_initial_vault_header(
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=(TEST_PARAMETERS),
        key_id=(b"K" * KEY_ID_LENGTH),
        wrapped_master_key=(_wrapped_master_key()),
    )

    assert header.version == VAULT_FORMAT_VERSION
    assert header.recovery_slots == ()


def test_create_initial_header_uses_a_fresh_vault_id() -> None:
    first = create_initial_vault_header(
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=(TEST_PARAMETERS),
        key_id=(b"K" * KEY_ID_LENGTH),
        wrapped_master_key=(_wrapped_master_key()),
    )
    second = create_initial_vault_header(
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=(TEST_PARAMETERS),
        key_id=(b"K" * KEY_ID_LENGTH),
        wrapped_master_key=(_wrapped_master_key()),
    )

    assert first.vault_id != second.vault_id


def test_find_password_usb_slot_returns_matching_slot() -> None:
    header = _header()

    found = header.find_password_usb_slot(b"K" * KEY_ID_LENGTH)

    assert found == header.key_slots[0]


def test_find_recovery_slot_returns_matching_slot() -> None:
    header = _header(recovery=True)

    found = header.find_recovery_slot(b"R" * RECOVERY_ID_LENGTH)

    assert found == header.recovery_slots[0]


def test_find_slots_return_none_for_unknown_ids() -> None:
    header = _header(recovery=True)

    assert header.find_password_usb_slot(b"X" * KEY_ID_LENGTH) is None
    assert header.find_recovery_slot(b"Y" * RECOVERY_ID_LENGTH) is None


def test_duplicate_key_ids_are_rejected() -> None:
    slot = _usb_slot()

    with pytest.raises(
        ValueError,
        match=("identifiers must be unique"),
    ):
        VaultHeader(
            vault_id=(b"V" * VAULT_ID_LENGTH),
            argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
            argon2_parameters=(TEST_PARAMETERS),
            key_slots=(
                slot,
                slot,
            ),
        )


def test_duplicate_recovery_ids_are_rejected() -> None:
    slot = _recovery_slot()

    with pytest.raises(
        ValueError,
        match=("identifiers must be unique"),
    ):
        VaultHeader(
            vault_id=(b"V" * VAULT_ID_LENGTH),
            argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
            argon2_parameters=(TEST_PARAMETERS),
            key_slots=(_usb_slot(),),
            recovery_slots=(
                slot,
                slot,
            ),
        )


def test_legacy_header_cannot_contain_recovery_slot() -> None:
    with pytest.raises(
        ValueError,
        match="legacy headers",
    ):
        _header(
            recovery=True,
            version=(LEGACY_VAULT_FORMAT_VERSION),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(
            {
                "magic": "WRONG",
            }
        ),
        lambda value: value.update(
            {
                "version": 999,
            }
        ),
        lambda value: value.update(
            {
                "vault_cipher": "unsupported",
            }
        ),
        lambda value: value["kdf"].update(
            {
                "name": "pbkdf2",
            }
        ),
        lambda value: value["kdf"].update(
            {
                "salt": "%%%",
            }
        ),
        lambda value: value["key_slots"][0].update(
            {
                "slot_type": "recovery",
            }
        ),
        lambda value: value["key_slots"][0].update(
            {
                "wrap_cipher": "unsupported",
            }
        ),
        lambda value: value["key_slots"][0].update(
            {
                "wrapped_master_key": "AA==",
            }
        ),
        lambda value: value["recovery_slots"][0].update(
            {
                "slot_type": "password_usb",
            }
        ),
        lambda value: value["recovery_slots"][0].update(
            {
                "recovery_id": "AA==",
            }
        ),
        lambda value: value.update(
            {
                "extra": True,
            }
        ),
        lambda value: value.pop("key_slots"),
        lambda value: value.pop("recovery_slots"),
    ],
)
def test_invalid_current_vault_headers_are_rejected(
    mutation: Mutation,
) -> None:
    payload: dict[
        str,
        Any,
    ] = json.loads(_header(recovery=True).to_bytes())

    mutation(payload)

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    with pytest.raises(
        VaultFormatError,
        match=(r"^Invalid vault header\.$"),
    ):
        VaultHeader.from_bytes(serialized)


def test_legacy_header_rejects_current_only_field() -> None:
    payload: dict[
        str,
        Any,
    ] = json.loads(_header(version=(LEGACY_VAULT_FORMAT_VERSION)).to_bytes())
    payload["recovery_slots"] = []

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    with pytest.raises(VaultFormatError):
        VaultHeader.from_bytes(serialized)


def test_empty_key_slot_list_is_rejected() -> None:
    payload = json.loads(_header().to_bytes())
    payload["key_slots"] = []

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    with pytest.raises(
        VaultFormatError,
        match=(r"^Invalid vault header\.$"),
    ):
        VaultHeader.from_bytes(serialized)
