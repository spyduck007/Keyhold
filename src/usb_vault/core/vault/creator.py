"""Create and verify a new empty encrypted vault."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from usb_vault.core.crypto.encryption import wrap_master_key
from usb_vault.core.crypto.key_derivation import (
    derive_key_encryption_key,
)
from usb_vault.core.crypto.password_kdf import (
    DEFAULT_ARGON2_PARAMETERS,
    Argon2Parameters,
    derive_password_key,
)
from usb_vault.core.crypto.payload_encryption import encrypt_payload
from usb_vault.core.crypto.random import (
    generate_argon2_salt,
    generate_master_key,
)
from usb_vault.core.keys.keyfile import create_usb_keyfile
from usb_vault.core.storage.container import VaultContainer
from usb_vault.core.storage.format import (
    create_initial_vault_header,
)
from usb_vault.core.storage.writer import (
    write_usb_keyfile,
    write_vault_container,
)
from usb_vault.core.vault.manifest import (
    create_empty_manifest,
    manifest_associated_data,
)
from usb_vault.core.vault.unlocker import unlock_vault


@dataclass(frozen=True, slots=True)
class CreateVaultResult:
    """Non-secret identifiers returned after successful vault creation."""

    vault_id: bytes
    key_id: bytes


def create_vault(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
    argon2_parameters: Argon2Parameters = (DEFAULT_ARGON2_PARAMETERS),
) -> CreateVaultResult:
    """Create, write, and verify an empty password-plus-USB vault."""
    vault_destination = Path(vault_path)
    keyfile_destination = Path(keyfile_path)

    if vault_destination.absolute() == keyfile_destination.absolute():
        raise ValueError("vault and keyfile paths must be different")

    if vault_destination.exists():
        raise FileExistsError(f"destination already exists: {vault_destination}")

    if keyfile_destination.exists():
        raise FileExistsError(f"destination already exists: {keyfile_destination}")

    keyfile = create_usb_keyfile()
    argon2_salt = generate_argon2_salt()
    master_key = generate_master_key()

    password_key = derive_password_key(
        password,
        argon2_salt,
        argon2_parameters,
    )
    key_encryption_key = derive_key_encryption_key(
        password_key,
        keyfile.secret,
    )
    wrapped_master_key = wrap_master_key(
        master_key,
        key_encryption_key,
    )
    header = create_initial_vault_header(
        argon2_salt=argon2_salt,
        argon2_parameters=argon2_parameters,
        key_id=keyfile.key_id,
        wrapped_master_key=wrapped_master_key,
    )
    manifest = create_empty_manifest()
    encrypted_manifest = encrypt_payload(
        manifest.to_bytes(),
        master_key,
        associated_data=manifest_associated_data(header.vault_id),
    )
    container = VaultContainer(
        header=header,
        encrypted_manifest=encrypted_manifest,
        storage_version=3,
    )

    keyfile_written = False
    vault_written = False

    try:
        write_usb_keyfile(
            keyfile_destination,
            keyfile,
        )
        keyfile_written = True

        write_vault_container(
            vault_destination,
            container,
        )
        vault_written = True

        with unlock_vault(
            vault_path=vault_destination,
            keyfile_path=keyfile_destination,
            password=password,
        ) as session:
            if session.header.vault_id != header.vault_id:
                raise RuntimeError("vault verification returned the wrong identifier")
    except Exception:
        if vault_written:
            _remove_created_file(vault_destination)

        if keyfile_written:
            _remove_created_file(keyfile_destination)

        raise

    return CreateVaultResult(
        vault_id=header.vault_id,
        key_id=keyfile.key_id,
    )


def _remove_created_file(path: Path) -> None:
    with suppress(FileNotFoundError):
        path.unlink()
