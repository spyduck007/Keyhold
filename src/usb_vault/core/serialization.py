"""Strict, deterministic serialization helpers for versioned vault data."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from typing import cast


def encode_base64(value: bytes) -> str:
    """Encode bytes using padded, standard Base64."""
    if not isinstance(value, bytes):
        raise TypeError("value must be bytes")

    return base64.b64encode(value).decode("ascii")


def decode_base64(value: object, *, field_name: str) -> bytes:
    """Decode a canonical Base64 string."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        raise ValueError(f"{field_name} is not valid Base64") from None

    if encode_base64(decoded) != value:
        raise ValueError(f"{field_name} is not canonical Base64")

    return decoded


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Serialize a JSON object deterministically as UTF-8 bytes."""
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def parse_json_object(data: bytes) -> dict[str, object]:
    """Parse a UTF-8 JSON object while rejecting duplicate keys."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")

    try:
        decoded = cast(
            object,
            json.loads(
                data.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError("invalid JSON object") from None

    if not isinstance(decoded, dict):
        raise ValueError("top-level JSON value must be an object")

    if not all(isinstance(key, str) for key in decoded):
        raise ValueError("JSON object keys must be strings")

    return cast(dict[str, object], decoded)


def require_exact_keys(
    value: Mapping[str, object],
    expected_keys: set[str],
    *,
    object_name: str,
) -> None:
    """Reject missing and unexpected keys in a serialized structure."""
    actual_keys = set(value)

    if actual_keys != expected_keys:
        raise ValueError(f"{object_name} contains unexpected or missing fields")


def require_object(
    value: object,
    *,
    field_name: str,
) -> dict[str, object]:
    """Return a JSON object after validating that all keys are strings."""
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be an object")

    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} keys must be strings")

    return cast(dict[str, object], value)


def require_list(
    value: object,
    *,
    field_name: str,
) -> list[object]:
    """Return a JSON list after strict type validation."""
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")

    return cast(list[object], value)


def require_string(
    value: object,
    *,
    field_name: str,
) -> str:
    """Return a JSON string after strict type validation."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    return value


def require_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    """Return a JSON integer while rejecting booleans."""
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")

    return cast(int, value)


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}

    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")

        result[key] = value

    return result
