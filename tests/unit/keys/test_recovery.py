"""Tests for printable recovery credentials."""

import pytest

from usb_vault.core.crypto.password_kdf import (
    PASSWORD_KEY_LENGTH,
)
from usb_vault.core.keys.recovery import (
    RECOVERY_CODE_PREFIX,
    RECOVERY_ID_LENGTH,
    RECOVERY_SECRET_LENGTH,
    RecoveryCredential,
    create_recovery_credential,
    derive_recovery_key_encryption_key,
    format_recovery_code,
    parse_recovery_code,
)

VAULT_ID = b"V" * 16
PASSWORD_KEY_A = b"P" * PASSWORD_KEY_LENGTH
PASSWORD_KEY_B = b"Q" * PASSWORD_KEY_LENGTH


def test_recovery_code_round_trip() -> None:
    credential = create_recovery_credential()

    code = credential.to_code()
    restored = parse_recovery_code(code)

    assert restored == credential
    assert code.startswith(f"{RECOVERY_CODE_PREFIX}-")
    assert len(credential.recovery_id) == RECOVERY_ID_LENGTH
    assert len(credential.secret) == RECOVERY_SECRET_LENGTH


def test_parser_accepts_lowercase_spaces_and_missing_hyphens() -> None:
    credential = RecoveryCredential(
        recovery_id=(b"I" * RECOVERY_ID_LENGTH),
        secret=(b"S" * RECOVERY_SECRET_LENGTH),
    )
    code = format_recovery_code(credential)
    relaxed = code.lower().replace(
        "-",
        " ",
    )

    assert parse_recovery_code(relaxed) == credential


def test_separate_recovery_credentials_are_independent() -> None:
    first = create_recovery_credential()
    second = create_recovery_credential()

    assert first.recovery_id != second.recovery_id
    assert first.secret != second.secret
    assert first.to_code() != second.to_code()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "UVR1",
        "WRONG-" + "A" * 64,
        "UVR1-" + "A" * 63,
        "UVR1-" + "0" * 64,
        "UVR1-" + "!" * 64,
    ],
)
def test_invalid_recovery_codes_are_rejected(
    value: str,
) -> None:
    with pytest.raises(ValueError):
        parse_recovery_code(value)


def test_same_inputs_derive_same_recovery_key() -> None:
    credential = RecoveryCredential(
        recovery_id=(b"I" * RECOVERY_ID_LENGTH),
        secret=(b"S" * RECOVERY_SECRET_LENGTH),
    )

    first = derive_recovery_key_encryption_key(
        PASSWORD_KEY_A,
        credential,
        vault_id=VAULT_ID,
    )
    second = derive_recovery_key_encryption_key(
        PASSWORD_KEY_A,
        credential,
        vault_id=VAULT_ID,
    )

    assert first == second
    assert len(first) == 32


def test_password_changes_recovery_key() -> None:
    credential = create_recovery_credential()

    first = derive_recovery_key_encryption_key(
        PASSWORD_KEY_A,
        credential,
        vault_id=VAULT_ID,
    )
    second = derive_recovery_key_encryption_key(
        PASSWORD_KEY_B,
        credential,
        vault_id=VAULT_ID,
    )

    assert first != second


def test_vault_identifier_changes_recovery_key() -> None:
    credential = create_recovery_credential()

    first = derive_recovery_key_encryption_key(
        PASSWORD_KEY_A,
        credential,
        vault_id=VAULT_ID,
    )
    second = derive_recovery_key_encryption_key(
        PASSWORD_KEY_A,
        credential,
        vault_id=b"X" * 16,
    )

    assert first != second
