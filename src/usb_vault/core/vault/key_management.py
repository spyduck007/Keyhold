"""Add, list, and revoke independently generated USB keys."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from usb_vault.core.crypto.encryption import wrap_master_key
from usb_vault.core.crypto.key_derivation import (
    derive_key_encryption_key,
)
from usb_vault.core.crypto.password_kdf import derive_password_key
from usb_vault.core.errors import (
    CurrentKeyRevocationError,
    KeySlotNotFoundError,
    LastKeySlotError,
    VaultOperationError,
)
from usb_vault.core.keys.keyfile import (
    KEY_ID_LENGTH,
    UsbKeyfile,
    create_usb_keyfile,
)
from usb_vault.core.storage.container import VaultContainer
from usb_vault.core.storage.format import (
    PasswordUsbKeySlot,
    VaultHeader,
)
from usb_vault.core.storage.reader import (
    read_usb_keyfile,
    read_vault_container,
)
from usb_vault.core.storage.writer import (
    write_usb_keyfile,
    write_vault_container,
)
from usb_vault.core.vault.unlocker import unlock_vault


@dataclass(frozen=True, slots=True)
class UsbKeySummary:
    """Public metadata describing one registered USB key."""

    key_id: bytes
    is_current: bool = False

    def __post_init__(self) -> None:
        _require_key_id(self.key_id)

        if type(self.is_current) is not bool:
            raise TypeError("is_current must be a boolean")

    @property
    def key_id_hex(self) -> str:
        """Return the key identifier as lowercase hexadecimal."""
        return format_key_id(self.key_id)


def list_usb_keys(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
) -> tuple[UsbKeySummary, ...]:
    """List registered USB keys after successfully unlocking the vault."""
    current_keyfile = read_usb_keyfile(keyfile_path)

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        ordered_slots = sorted(
            session.header.key_slots,
            key=lambda slot: slot.key_id,
        )

        return tuple(
            UsbKeySummary(
                key_id=slot.key_id,
                is_current=(slot.key_id == current_keyfile.key_id),
            )
            for slot in ordered_slots
        )


def add_usb_key(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
    new_keyfile_path: str | Path,
) -> UsbKeySummary:
    """Add an independently generated USB key slot."""
    vault_destination = Path(vault_path)
    new_keyfile_destination = Path(new_keyfile_path)

    if vault_destination.absolute() == new_keyfile_destination.absolute():
        raise ValueError("vault and keyfile paths must be different")

    if new_keyfile_destination.exists():
        raise FileExistsError(f"destination already exists: {new_keyfile_destination}")

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        original_container = read_vault_container(vault_path)

        _require_matching_header(
            original_container,
            session.header,
        )

        existing_key_ids = {slot.key_id for slot in session.header.key_slots}
        new_keyfile = _create_unique_keyfile(existing_key_ids)

        master_key = session.copy_master_key()
        password_key = derive_password_key(
            password,
            session.header.argon2_salt,
            session.header.argon2_parameters,
        )
        key_encryption_key = derive_key_encryption_key(
            password_key,
            new_keyfile.secret,
        )
        wrapped_master_key = wrap_master_key(
            master_key,
            key_encryption_key,
        )

        new_slot = PasswordUsbKeySlot(
            key_id=new_keyfile.key_id,
            wrapped_master_key=(wrapped_master_key),
        )
        updated_header = _copy_header_with_slots(
            session.header,
            (
                *session.header.key_slots,
                new_slot,
            ),
        )
        updated_container = VaultContainer(
            header=updated_header,
            encrypted_manifest=(original_container.encrypted_manifest),
            blobs=original_container.blobs,
        )

        keyfile_written = False
        vault_updated = False

        try:
            write_usb_keyfile(
                new_keyfile_destination,
                new_keyfile,
            )
            keyfile_written = True

            write_vault_container(
                vault_path,
                updated_container,
                overwrite=True,
            )
            vault_updated = True

            with unlock_vault(
                vault_path=vault_path,
                keyfile_path=(new_keyfile_destination),
                password=password,
            ) as verification:
                if verification.header.vault_id != session.header.vault_id:
                    raise RuntimeError("backup USB verification opened the wrong vault")

                if verification.header.find_password_usb_slot(new_keyfile.key_id) is None:
                    raise RuntimeError("backup USB verification did not find its key slot")
        except Exception:
            try:
                if vault_updated:
                    write_vault_container(
                        vault_path,
                        original_container,
                        overwrite=True,
                    )
            finally:
                if keyfile_written:
                    with suppress(FileNotFoundError):
                        new_keyfile_destination.unlink()

            raise

        return UsbKeySummary(
            key_id=new_keyfile.key_id,
        )


def revoke_usb_key(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: str | bytes | bytearray | memoryview,
    target_key_id: bytes,
) -> UsbKeySummary:
    """Revoke a non-current USB key while preserving other keys."""
    _require_key_id(target_key_id)

    current_keyfile = read_usb_keyfile(keyfile_path)

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        target_slot = session.header.find_password_usb_slot(target_key_id)

        if target_slot is None:
            raise KeySlotNotFoundError("USB key is not registered.")

        if len(session.header.key_slots) <= 1:
            raise LastKeySlotError("The final USB key cannot be revoked.")

        if target_key_id == current_keyfile.key_id:
            raise CurrentKeyRevocationError(
                "The USB key currently being used "
                "cannot be revoked. Unlock with "
                "another registered USB key first."
            )

        original_container = read_vault_container(vault_path)

        _require_matching_header(
            original_container,
            session.header,
        )

        remaining_slots = tuple(
            slot for slot in session.header.key_slots if slot.key_id != target_key_id
        )
        updated_header = _copy_header_with_slots(
            session.header,
            remaining_slots,
        )
        updated_container = VaultContainer(
            header=updated_header,
            encrypted_manifest=(original_container.encrypted_manifest),
            blobs=original_container.blobs,
        )

        vault_updated = False

        try:
            write_vault_container(
                vault_path,
                updated_container,
                overwrite=True,
            )
            vault_updated = True

            with unlock_vault(
                vault_path=vault_path,
                keyfile_path=keyfile_path,
                password=password,
            ) as verification:
                if verification.header.vault_id != session.header.vault_id:
                    raise RuntimeError("key revocation verification opened the wrong vault")

                if verification.header.find_password_usb_slot(target_key_id) is not None:
                    raise RuntimeError("revoked USB key slot is still present")
        except Exception:
            if vault_updated:
                write_vault_container(
                    vault_path,
                    original_container,
                    overwrite=True,
                )

            raise

        return UsbKeySummary(
            key_id=target_key_id,
        )


def format_key_id(
    key_id: bytes,
) -> str:
    """Encode a non-secret key identifier for CLI display."""
    _require_key_id(key_id)
    return key_id.hex()


def parse_key_id_hex(
    value: str,
) -> bytes:
    """Parse the exact hexadecimal representation of a key ID."""
    if not isinstance(value, str):
        raise TypeError("key ID must be a string")

    expected_length = KEY_ID_LENGTH * 2

    if len(value) != expected_length:
        raise ValueError(f"key ID must contain exactly {expected_length} hexadecimal characters")

    try:
        key_id = bytes.fromhex(value)
    except ValueError:
        raise ValueError("key ID must contain only hexadecimal characters") from None

    _require_key_id(key_id)
    return key_id


def _create_unique_keyfile(
    existing_key_ids: set[bytes],
) -> UsbKeyfile:
    for _ in range(16):
        keyfile = create_usb_keyfile()

        if keyfile.key_id not in existing_key_ids:
            return keyfile

    raise RuntimeError("unable to generate a unique USB key identifier")


def _copy_header_with_slots(
    header: VaultHeader,
    key_slots: tuple[
        PasswordUsbKeySlot,
        ...,
    ],
) -> VaultHeader:
    return VaultHeader(
        vault_id=header.vault_id,
        argon2_salt=header.argon2_salt,
        argon2_parameters=(header.argon2_parameters),
        key_slots=key_slots,
        version=header.version,
        vault_cipher=header.vault_cipher,
    )


def _require_matching_header(
    container: VaultContainer,
    header: VaultHeader,
) -> None:
    if container.header != header:
        raise VaultOperationError("Vault changed during the operation.")


def _require_key_id(
    key_id: bytes,
) -> None:
    if not isinstance(key_id, bytes):
        raise TypeError("key_id must be bytes")

    if len(key_id) != KEY_ID_LENGTH:
        raise ValueError(f"key_id must be exactly {KEY_ID_LENGTH} bytes")
