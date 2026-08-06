"""Tests for the versioned USB keyfile format."""

import json

import pytest

from usb_vault.core.crypto.random import USB_SECRET_LENGTH
from usb_vault.core.errors import VaultFormatError
from usb_vault.core.keys.keyfile import (
    KEYFILE_MAGIC,
    KEYFILE_VERSION,
    KEY_ID_LENGTH,
    UsbKeyfile,
    create_usb_keyfile,
)


def test_create_usb_keyfile_generates_expected_lengths() -> None:
    keyfile = create_usb_keyfile()

    assert len(keyfile.key_id) == KEY_ID_LENGTH
    assert len(keyfile.secret) == USB_SECRET_LENGTH
    assert keyfile.version == KEYFILE_VERSION


def test_separate_keyfiles_use_independent_random_values() -> None:
    first = create_usb_keyfile()
    second = create_usb_keyfile()

    assert first.key_id != second.key_id
    assert first.secret != second.secret


def test_keyfile_round_trip() -> None:
    original = create_usb_keyfile()

    restored = UsbKeyfile.from_bytes(original.to_bytes())

    assert restored == original


def test_keyfile_serialization_is_deterministic() -> None:
    keyfile = UsbKeyfile(
        key_id=b"K" * KEY_ID_LENGTH,
        secret=b"S" * USB_SECRET_LENGTH,
    )

    assert keyfile.to_bytes() == keyfile.to_bytes()


def test_serialized_keyfile_contains_expected_metadata() -> None:
    keyfile = create_usb_keyfile()
    payload = json.loads(keyfile.to_bytes())

    assert payload["magic"] == KEYFILE_MAGIC
    assert payload["version"] == KEYFILE_VERSION
    assert set(payload) == {
        "magic",
        "version",
        "key_id",
        "secret",
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        (b'{"magic":"WRONG","version":1,"key_id":"AA==","secret":"AA=="}'),
        (b'{"magic":"USBVAULTKEY","version":2,"key_id":"AA==","secret":"AA=="}'),
        (b'{"magic":"USBVAULTKEY","version":1,"key_id":"%%%","secret":"AA=="}'),
        (b'{"magic":"USBVAULTKEY","version":1,"key_id":"AA=="}'),
        (
            b'{"magic":"USBVAULTKEY","version":1,'
            b'"key_id":"AAAAAAAAAAAAAAAAAAAAAA==",'
            b'"secret":'
            b'"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",'
            b'"extra":true}'
        ),
    ],
)
def test_invalid_keyfiles_are_rejected(
    payload: bytes,
) -> None:
    with pytest.raises(
        VaultFormatError,
        match=r"^Invalid USB keyfile\.$",
    ):
        UsbKeyfile.from_bytes(payload)


def test_duplicate_json_fields_are_rejected() -> None:
    payload = (
        b'{"magic":"USBVAULTKEY",'
        b'"magic":"USBVAULTKEY",'
        b'"version":1,'
        b'"key_id":"AAAAAAAAAAAAAAAAAAAAAA==",'
        b'"secret":'
        b'"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}'
    )

    with pytest.raises(
        VaultFormatError,
        match=r"^Invalid USB keyfile\.$",
    ):
        UsbKeyfile.from_bytes(payload)
