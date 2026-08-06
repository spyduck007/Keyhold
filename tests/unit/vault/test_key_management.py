"""Tests for USB key identifier formatting and parsing."""

import pytest

from usb_vault.core.keys.keyfile import KEY_ID_LENGTH
from usb_vault.core.vault.key_management import (
    UsbKeySummary,
    format_key_id,
    parse_key_id_hex,
)


def test_key_id_hex_round_trip() -> None:
    key_id = bytes(range(KEY_ID_LENGTH))

    encoded = format_key_id(key_id)
    restored = parse_key_id_hex(encoded)

    assert restored == key_id
    assert len(encoded) == 32


def test_uppercase_key_id_is_accepted() -> None:
    key_id = b"K" * KEY_ID_LENGTH

    restored = parse_key_id_hex(key_id.hex().upper())

    assert restored == key_id


@pytest.mark.parametrize(
    "value",
    [
        "",
        "00",
        "0" * 31,
        "0" * 33,
        "g" * 32,
        "-" * 32,
    ],
)
def test_invalid_key_id_text_is_rejected(
    value: str,
) -> None:
    with pytest.raises(ValueError):
        parse_key_id_hex(value)


def test_key_summary_exposes_hex_identifier() -> None:
    key_id = b"A" * KEY_ID_LENGTH
    summary = UsbKeySummary(
        key_id=key_id,
        is_current=True,
    )

    assert summary.key_id_hex == key_id.hex()
    assert summary.is_current
