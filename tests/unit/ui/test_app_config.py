"""Tests for desktop monitoring environment configuration."""

import pytest

from usb_vault.ui.app import (
    _environment_duration_ms,
    _vault_paths_from_arguments,
)


def test_missing_environment_value_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variable_name = "USB_VAULT_TEST_DURATION"
    monkeypatch.delenv(
        variable_name,
        raising=False,
    )

    assert (
        _environment_duration_ms(
            variable_name,
            5_000,
        )
        == 5_000
    )


def test_environment_seconds_are_converted_to_milliseconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variable_name = "USB_VAULT_TEST_DURATION"
    monkeypatch.setenv(
        variable_name,
        "12",
    )

    assert (
        _environment_duration_ms(
            variable_name,
            5_000,
        )
        == 12_000
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0",
        "-1",
        "1.5",
        "ten",
    ],
)
def test_invalid_environment_duration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    variable_name = "USB_VAULT_TEST_DURATION"
    monkeypatch.setenv(
        variable_name,
        value,
    )

    with pytest.raises(
        RuntimeError,
        match="positive whole number",
    ):
        _environment_duration_ms(
            variable_name,
            5_000,
        )


def test_vault_paths_from_arguments_keeps_only_vault_files() -> None:
    assert _vault_paths_from_arguments(
        [
            "/Users/ansh/Downloads/Private.vault",
            "--flag",
            "/Users/ansh/notes.txt",
            "/Volumes/USB/Backup.vault",
        ]
    ) == [
        "/Users/ansh/Downloads/Private.vault",
        "/Volumes/USB/Backup.vault",
    ]


def test_vault_paths_from_arguments_returns_empty_for_no_matches() -> None:
    assert _vault_paths_from_arguments(["--flag", "value"]) == []
