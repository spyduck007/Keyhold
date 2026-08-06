"""Tests for the CLI rename command."""

from pathlib import Path

import pytest

from usb_vault.cli.commands import (
    rename as rename_command,
)
from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)


def test_rename_command_prompts_and_reports_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[
        str,
        object,
    ] = {}

    def fake_getpass(
        prompt: str,
    ) -> str:
        assert prompt == "Password: "
        return "test password"

    def fake_rename_file(
        *,
        vault_path: str | Path,
        keyfile_path: str | Path,
        password: (str | bytes | bytearray | memoryview),
        stored_name: str,
        new_name: str,
    ) -> VaultEntrySummary:
        captured.update(
            {
                "vault_path": vault_path,
                "keyfile_path": (keyfile_path),
                "password": password,
                "stored_name": (stored_name),
                "new_name": new_name,
            }
        )

        return VaultEntrySummary(
            name=new_name,
            size=12,
        )

    monkeypatch.setattr(
        rename_command,
        "getpass",
        fake_getpass,
    )
    monkeypatch.setattr(
        rename_command,
        "rename_file",
        fake_rename_file,
    )

    result = rename_command.run_rename_command(
        vault_path=Path("/tmp/Private.vault"),
        keyfile_path=Path("/tmp/.authkey"),
        stored_name="old.txt",
        new_name="new.txt",
    )

    assert result == 0
    assert captured == {
        "vault_path": Path("/tmp/Private.vault"),
        "keyfile_path": Path("/tmp/.authkey"),
        "password": "test password",
        "stored_name": "old.txt",
        "new_name": "new.txt",
    }
    assert capsys.readouterr().out == ("Renamed: old.txt -> new.txt\n")
