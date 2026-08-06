"""Tests for mounted macOS USB-key discovery."""

from pathlib import Path

from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.vault.creator import (
    create_vault,
)
from usb_vault.platform.macos.usb_discovery import (
    MacOsUsbKeyLocator,
)

PASSWORD = "correct horse battery staple"

TEST_PARAMETERS = Argon2Parameters(
    memory_cost_kib=1_024,
    time_cost=1,
    parallelism=1,
)


def _create_test_vault(
    *,
    vault_path: Path,
    keyfile_path: Path,
) -> None:
    keyfile_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    create_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=PASSWORD,
        argon2_parameters=(TEST_PARAMETERS),
    )


def test_locator_finds_registered_hidden_keyfile(
    tmp_path: Path,
) -> None:
    volumes_root = tmp_path / "Volumes"
    usb_root = volumes_root / "SchoolUSB"
    usb_root.mkdir(parents=True)

    vault_path = tmp_path / "Private.vault"
    keyfile_path = usb_root / ".authkey"

    _create_test_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
    )

    locator = MacOsUsbKeyLocator(volumes_root=volumes_root)

    assert locator.find_matching_keyfile(vault_path) == keyfile_path


def test_locator_finds_named_authkey(
    tmp_path: Path,
) -> None:
    volumes_root = tmp_path / "Volumes"
    usb_root = volumes_root / "BackupUSB"
    usb_root.mkdir(parents=True)

    vault_path = tmp_path / "Private.vault"
    keyfile_path = usb_root / "school-vault.authkey"

    _create_test_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
    )

    locator = MacOsUsbKeyLocator(volumes_root=volumes_root)

    assert locator.find_matching_keyfile(vault_path) == keyfile_path


def test_locator_ignores_unregistered_valid_key(
    tmp_path: Path,
) -> None:
    volumes_root = tmp_path / "Volumes"
    usb_root = volumes_root / "WrongUSB"
    usb_root.mkdir(parents=True)

    target_vault_path = tmp_path / "Target.vault"
    target_keyfile_path = tmp_path / "target.authkey"

    _create_test_vault(
        vault_path=target_vault_path,
        keyfile_path=target_keyfile_path,
    )

    unrelated_vault_path = tmp_path / "Other.vault"
    unrelated_keyfile_path = usb_root / ".authkey"

    _create_test_vault(
        vault_path=unrelated_vault_path,
        keyfile_path=(unrelated_keyfile_path),
    )

    locator = MacOsUsbKeyLocator(volumes_root=volumes_root)

    assert locator.find_matching_keyfile(target_vault_path) is None


def test_locator_does_not_search_nested_directories(
    tmp_path: Path,
) -> None:
    volumes_root = tmp_path / "Volumes"
    nested_directory = volumes_root / "SchoolUSB" / "keys"
    nested_directory.mkdir(parents=True)

    vault_path = tmp_path / "Private.vault"
    keyfile_path = nested_directory / ".authkey"

    _create_test_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
    )

    locator = MacOsUsbKeyLocator(volumes_root=volumes_root)

    assert locator.find_matching_keyfile(vault_path) is None


def test_missing_volumes_root_returns_no_match(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "Private.vault"
    keyfile_path = tmp_path / ".authkey"

    _create_test_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
    )

    locator = MacOsUsbKeyLocator(volumes_root=(tmp_path / "MissingVolumes"))

    assert locator.find_matching_keyfile(vault_path) is None
