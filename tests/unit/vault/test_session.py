"""Tests for unlocked vault-session lifecycle."""

from pathlib import Path

import pytest

from usb_vault.core.crypto.encryption import WrappedMasterKey
from usb_vault.core.crypto.password_kdf import Argon2Parameters
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    ARGON2_SALT_LENGTH,
)
from usb_vault.core.keys.keyfile import KEY_ID_LENGTH
from usb_vault.core.storage.format import (
    VAULT_ID_LENGTH,
    PasswordUsbKeySlot,
    VaultHeader,
)
from usb_vault.core.vault.manifest import VaultManifest
from usb_vault.core.vault.session import VaultSession

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def _header() -> VaultHeader:
    return VaultHeader(
        vault_id=b"V" * VAULT_ID_LENGTH,
        argon2_salt=(b"S" * ARGON2_SALT_LENGTH),
        argon2_parameters=TEST_PARAMETERS,
        key_slots=(
            PasswordUsbKeySlot(
                key_id=b"K" * KEY_ID_LENGTH,
                wrapped_master_key=(
                    WrappedMasterKey(
                        nonce=(b"N" * AES_GCM_NONCE_LENGTH),
                        ciphertext=b"C" * 48,
                    )
                ),
            ),
        ),
    )


def test_session_context_manager_closes_session() -> None:
    session = VaultSession.create(
        vault_path=Path("test.vault"),
        header=_header(),
        manifest=VaultManifest(),
        master_key=b"M" * 32,
    )

    with session as opened:
        assert opened.entry_count == 0
        assert not opened.is_closed

    assert session.is_closed


def test_closed_session_rejects_operations() -> None:
    session = VaultSession.create(
        vault_path=Path("test.vault"),
        header=_header(),
        manifest=VaultManifest(),
        master_key=b"M" * 32,
    )
    session.close()

    with pytest.raises(
        RuntimeError,
        match="session is closed",
    ):
        _ = session.entry_count


def test_close_is_idempotent() -> None:
    session = VaultSession.create(
        vault_path=Path("test.vault"),
        header=_header(),
        manifest=VaultManifest(),
        master_key=b"M" * 32,
    )

    session.close()
    session.close()

    assert session.is_closed
