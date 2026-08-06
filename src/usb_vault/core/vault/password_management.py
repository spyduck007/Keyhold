"""Secure password rotation for every registered USB key slot."""

from __future__ import annotations

import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from usb_vault.core.crypto.encryption import wrap_master_key
from usb_vault.core.crypto.key_derivation import (
    derive_key_encryption_key,
)
from usb_vault.core.crypto.password_kdf import derive_password_key
from usb_vault.core.crypto.random import (
    generate_argon2_salt,
)
from usb_vault.core.errors import (
    KeyfileSetError,
    VaultOperationError,
)
from usb_vault.core.keys.keyfile import UsbKeyfile
from usb_vault.core.storage.container import VaultContainer
from usb_vault.core.storage.format import (
    PasswordUsbKeySlot,
    VaultHeader,
)
from usb_vault.core.storage.reader import (
    read_usb_keyfile,
    read_vault_container,
)
from usb_vault.core.storage.writer import write_vault_container
from usb_vault.core.vault.unlocker import unlock_vault

PasswordInput = str | bytes | bytearray | memoryview


@dataclass(frozen=True, slots=True)
class PasswordChangeResult:
    """Non-secret result returned after password rotation."""

    vault_id: bytes
    key_count: int

    def __post_init__(self) -> None:
        if not isinstance(
            self.vault_id,
            bytes,
        ):
            raise TypeError("vault_id must be bytes")

        if type(self.key_count) is not int:
            raise TypeError("key_count must be an integer")

        if self.key_count <= 0:
            raise ValueError("key_count must be greater than zero")


def change_vault_password(
    *,
    vault_path: str | Path,
    current_keyfile_path: str | Path,
    current_password: PasswordInput,
    new_password: PasswordInput,
    additional_keyfile_paths: Sequence[str | Path] = (),
) -> PasswordChangeResult:
    """Re-wrap the master key for every USB using a new password."""
    current_path = Path(current_keyfile_path)

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=current_path,
        password=current_password,
    ) as session:
        if hmac.compare_digest(
            _password_bytes(current_password),
            _password_bytes(new_password),
        ):
            raise ValueError("new password must differ from the current password")

        original_container = read_vault_container(vault_path)

        _require_matching_header(
            original_container,
            session.header,
        )

        supplied_paths = (
            current_path,
            *(Path(path) for path in (additional_keyfile_paths)),
        )
        loaded_keyfiles = _load_unique_keyfiles(supplied_paths)

        keyfiles_by_id = {
            keyfile.key_id: (
                keyfile_path,
                keyfile,
            )
            for (
                keyfile_path,
                keyfile,
            ) in loaded_keyfiles
        }

        registered_key_ids = {slot.key_id for slot in (session.header.key_slots)}
        supplied_key_ids = set(keyfiles_by_id)

        if supplied_key_ids != registered_key_ids:
            raise KeyfileSetError("Provide exactly one keyfile for every registered USB key.")

        new_argon2_salt = generate_argon2_salt()
        new_password_key = derive_password_key(
            new_password,
            new_argon2_salt,
            session.header.argon2_parameters,
        )
        master_key = session.copy_master_key()

        updated_slots: list[PasswordUsbKeySlot] = []

        for existing_slot in session.header.key_slots:
            (
                _,
                keyfile,
            ) = keyfiles_by_id[existing_slot.key_id]

            key_encryption_key = derive_key_encryption_key(
                new_password_key,
                keyfile.secret,
            )
            wrapped_master_key = wrap_master_key(
                master_key,
                key_encryption_key,
            )

            updated_slots.append(
                PasswordUsbKeySlot(
                    key_id=(existing_slot.key_id),
                    wrapped_master_key=(wrapped_master_key),
                )
            )

        updated_header = VaultHeader(
            vault_id=(session.header.vault_id),
            argon2_salt=(new_argon2_salt),
            argon2_parameters=(session.header.argon2_parameters),
            key_slots=tuple(updated_slots),
            version=(session.header.version),
            vault_cipher=(session.header.vault_cipher),
        )
        updated_container = VaultContainer(
            header=updated_header,
            encrypted_manifest=(original_container.encrypted_manifest),
            blobs=(original_container.blobs),
        )

        vault_updated = False

        try:
            write_vault_container(
                vault_path,
                updated_container,
                overwrite=True,
            )
            vault_updated = True

            for updated_slot in updated_header.key_slots:
                (
                    verification_path,
                    _,
                ) = keyfiles_by_id[updated_slot.key_id]

                with unlock_vault(
                    vault_path=(vault_path),
                    keyfile_path=(verification_path),
                    password=(new_password),
                ) as verification:
                    if verification.header.vault_id != session.header.vault_id:
                        raise RuntimeError("password-change verification opened the wrong vault")

                    if verification.header.find_password_usb_slot(updated_slot.key_id) is None:
                        raise RuntimeError("password-change verification could not find a key slot")
        except Exception:
            if vault_updated:
                write_vault_container(
                    vault_path,
                    original_container,
                    overwrite=True,
                )

            raise

        return PasswordChangeResult(
            vault_id=(updated_header.vault_id),
            key_count=len(updated_header.key_slots),
        )


def _load_unique_keyfiles(
    paths: Sequence[Path],
) -> tuple[
    tuple[Path, UsbKeyfile],
    ...,
]:
    loaded: list[tuple[Path, UsbKeyfile]] = []
    seen_key_ids: set[bytes] = set()

    for path in paths:
        keyfile = read_usb_keyfile(path)

        if keyfile.key_id in seen_key_ids:
            raise KeyfileSetError("Each registered USB keyfile must be supplied exactly once.")

        seen_key_ids.add(keyfile.key_id)
        loaded.append(
            (
                path,
                keyfile,
            )
        )

    return tuple(loaded)


def _password_bytes(
    password: PasswordInput,
) -> bytes:
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    elif isinstance(
        password,
        (
            bytes,
            bytearray,
            memoryview,
        ),
    ):
        password_bytes = bytes(password)
    else:
        raise TypeError("password must be str or bytes-like")

    if not password_bytes:
        raise ValueError("password must not be empty")

    return password_bytes


def _require_matching_header(
    container: VaultContainer,
    header: VaultHeader,
) -> None:
    if container.header != header:
        raise VaultOperationError("Vault changed during the password operation.")
