"""Create, verify, rotate, and use password-protected recovery codes."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from usb_vault.core.crypto.encryption import (
    unwrap_master_key,
    wrap_master_key,
)
from usb_vault.core.crypto.key_derivation import (
    derive_key_encryption_key,
)
from usb_vault.core.crypto.password_kdf import (
    derive_password_key,
)
from usb_vault.core.errors import (
    RecoveryAlreadyConfiguredError,
    UnlockError,
    VaultOperationError,
)
from usb_vault.core.keys.keyfile import (
    UsbKeyfile,
    create_usb_keyfile,
)
from usb_vault.core.keys.recovery import (
    RecoveryCredential,
    create_recovery_credential,
    derive_recovery_key_encryption_key,
    parse_recovery_code,
)
from usb_vault.core.storage.container import (
    VaultContainer,
)
from usb_vault.core.storage.format import (
    VAULT_FORMAT_VERSION,
    PasswordUsbKeySlot,
    RecoveryKeySlot,
    VaultHeader,
)
from usb_vault.core.storage.reader import (
    read_vault_container,
)
from usb_vault.core.storage.writer import (
    write_usb_keyfile,
    write_vault_container,
)
from usb_vault.core.vault.session import (
    VaultSession,
)
from usb_vault.core.vault.unlocker import (
    open_vault_session,
    unlock_vault,
)

PasswordInput = str | bytes | bytearray | memoryview


@dataclass(frozen=True, slots=True)
class RecoveryCodeResult:
    """The new recovery code and its non-secret ID."""

    recovery_code: str
    recovery_id: bytes
    replaced_existing: bool

    def __post_init__(self) -> None:
        if not isinstance(
            self.recovery_code,
            str,
        ):
            raise TypeError("recovery_code must be a string")

        if not isinstance(
            self.recovery_id,
            bytes,
        ):
            raise TypeError("recovery_id must be bytes")

        if type(self.replaced_existing) is not bool:
            raise TypeError("replaced_existing must be a boolean")


@dataclass(frozen=True, slots=True)
class RecoveryUsbResult:
    """Result of restoring USB access with a rotated code."""

    key_id: bytes
    recovery_code: str
    replaced_existing_keys: bool

    def __post_init__(self) -> None:
        if not isinstance(
            self.key_id,
            bytes,
        ):
            raise TypeError("key_id must be bytes")

        if not isinstance(
            self.recovery_code,
            str,
        ):
            raise TypeError("recovery_code must be a string")

        if type(self.replaced_existing_keys) is not bool:
            raise TypeError("replaced_existing_keys must be a boolean")


def create_recovery_code(
    *,
    vault_path: str | Path,
    keyfile_path: str | Path,
    password: PasswordInput,
    replace: bool = False,
) -> RecoveryCodeResult:
    """Create or explicitly rotate the vault recovery code."""
    if type(replace) is not bool:
        raise TypeError("replace must be a boolean")

    with unlock_vault(
        vault_path=vault_path,
        keyfile_path=keyfile_path,
        password=password,
    ) as session:
        replaced_existing = bool(session.header.recovery_slots)

        if replaced_existing and not replace:
            raise RecoveryAlreadyConfiguredError(
                "Recovery is already configured. Use the rotation command to replace it."
            )

        original_container = read_vault_container(vault_path)
        _require_matching_header(
            original_container,
            session.header,
        )

        credential = create_recovery_credential()
        master_key = session.copy_master_key()
        password_key = derive_password_key(
            password,
            session.header.argon2_salt,
            session.header.argon2_parameters,
        )
        recovery_key = derive_recovery_key_encryption_key(
            password_key,
            credential,
            vault_id=(session.header.vault_id),
        )
        recovery_slot = RecoveryKeySlot(
            recovery_id=(credential.recovery_id),
            wrapped_master_key=(
                wrap_master_key(
                    master_key,
                    recovery_key,
                )
            ),
        )
        updated_header = _copy_header(
            session.header,
            recovery_slots=(recovery_slot,),
        )
        updated_container = VaultContainer(
            header=updated_header,
            encrypted_manifest=(original_container.encrypted_manifest),
            blobs=original_container.blobs,
        )
        recovery_code = credential.to_code()
        vault_updated = False

        try:
            write_vault_container(
                vault_path,
                updated_container,
                overwrite=True,
            )
            vault_updated = True

            with unlock_vault_with_recovery(
                vault_path=vault_path,
                password=password,
                recovery_code=recovery_code,
            ) as verification:
                if verification.header.vault_id != session.header.vault_id:
                    raise RuntimeError("recovery verification opened the wrong vault")
        except Exception:
            if vault_updated:
                write_vault_container(
                    vault_path,
                    original_container,
                    overwrite=True,
                )

            raise

        return RecoveryCodeResult(
            recovery_code=recovery_code,
            recovery_id=(credential.recovery_id),
            replaced_existing=(replaced_existing),
        )


def unlock_vault_with_recovery(
    *,
    vault_path: str | Path,
    password: PasswordInput,
    recovery_code: str,
) -> VaultSession:
    """Unlock using the password and offline recovery code."""
    try:
        credential = parse_recovery_code(recovery_code)
        container = read_vault_container(vault_path)
        slot = container.header.find_recovery_slot(credential.recovery_id)

        if slot is None:
            raise UnlockError

        password_key = derive_password_key(
            password,
            container.header.argon2_salt,
            container.header.argon2_parameters,
        )
        recovery_key = derive_recovery_key_encryption_key(
            password_key,
            credential,
            vault_id=(container.header.vault_id),
        )
        master_key = unwrap_master_key(
            slot.wrapped_master_key,
            recovery_key,
        )
    except UnlockError:
        raise
    except (
        TypeError,
        ValueError,
    ):
        raise UnlockError from None

    return open_vault_session(
        vault_path=vault_path,
        container=container,
        master_key=master_key,
    )


def recover_usb_key(
    *,
    vault_path: str | Path,
    password: PasswordInput,
    recovery_code: str,
    new_keyfile_path: str | Path,
    replace_existing_keys: bool = False,
) -> RecoveryUsbResult:
    """Create a new USB key and rotate recovery after use."""
    if type(replace_existing_keys) is not bool:
        raise TypeError("replace_existing_keys must be a boolean")

    new_keyfile_destination = Path(new_keyfile_path)

    if new_keyfile_destination.exists():
        raise FileExistsError(f"destination already exists: {new_keyfile_destination}")

    old_credential = _parse_recovery_or_unlock_error(recovery_code)

    with unlock_vault_with_recovery(
        vault_path=vault_path,
        password=password,
        recovery_code=recovery_code,
    ) as session:
        original_container = read_vault_container(vault_path)
        _require_matching_header(
            original_container,
            session.header,
        )

        if session.header.find_recovery_slot(old_credential.recovery_id) is None:
            raise UnlockError

        existing_key_ids = {slot.key_id for slot in (session.header.key_slots)}
        new_keyfile = _create_unique_keyfile(existing_key_ids)
        master_key = session.copy_master_key()
        password_key = derive_password_key(
            password,
            session.header.argon2_salt,
            session.header.argon2_parameters,
        )
        usb_key = derive_key_encryption_key(
            password_key,
            new_keyfile.secret,
        )
        new_usb_slot = PasswordUsbKeySlot(
            key_id=new_keyfile.key_id,
            wrapped_master_key=(
                wrap_master_key(
                    master_key,
                    usb_key,
                )
            ),
        )

        if replace_existing_keys:
            updated_usb_slots = (new_usb_slot,)
        else:
            updated_usb_slots = (
                *session.header.key_slots,
                new_usb_slot,
            )

        new_credential = create_recovery_credential()
        new_recovery_key = derive_recovery_key_encryption_key(
            password_key,
            new_credential,
            vault_id=(session.header.vault_id),
        )
        new_recovery_slot = RecoveryKeySlot(
            recovery_id=(new_credential.recovery_id),
            wrapped_master_key=(
                wrap_master_key(
                    master_key,
                    new_recovery_key,
                )
            ),
        )
        updated_header = _copy_header(
            session.header,
            key_slots=updated_usb_slots,
            recovery_slots=(new_recovery_slot,),
        )
        updated_container = VaultContainer(
            header=updated_header,
            encrypted_manifest=(original_container.encrypted_manifest),
            blobs=original_container.blobs,
        )
        new_recovery_code = new_credential.to_code()

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
            ) as usb_verification:
                if usb_verification.header.vault_id != session.header.vault_id:
                    raise RuntimeError("recovered USB opened the wrong vault")

            with unlock_vault_with_recovery(
                vault_path=vault_path,
                password=password,
                recovery_code=(new_recovery_code),
            ) as recovery_verification:
                if recovery_verification.header.vault_id != session.header.vault_id:
                    raise RuntimeError("rotated recovery code opened the wrong vault")
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

        return RecoveryUsbResult(
            key_id=new_keyfile.key_id,
            recovery_code=(new_recovery_code),
            replaced_existing_keys=(replace_existing_keys),
        )


def _copy_header(
    header: VaultHeader,
    *,
    key_slots: tuple[
        PasswordUsbKeySlot,
        ...,
    ]
    | None = None,
    recovery_slots: tuple[
        RecoveryKeySlot,
        ...,
    ]
    | None = None,
) -> VaultHeader:
    return VaultHeader(
        vault_id=header.vault_id,
        argon2_salt=header.argon2_salt,
        argon2_parameters=(header.argon2_parameters),
        key_slots=(header.key_slots if key_slots is None else key_slots),
        recovery_slots=(header.recovery_slots if recovery_slots is None else recovery_slots),
        version=VAULT_FORMAT_VERSION,
        vault_cipher=header.vault_cipher,
    )


def _create_unique_keyfile(
    existing_key_ids: set[bytes],
) -> UsbKeyfile:
    for _ in range(16):
        keyfile = create_usb_keyfile()

        if keyfile.key_id not in existing_key_ids:
            return keyfile

    raise RuntimeError("unable to generate a unique USB key identifier")


def _parse_recovery_or_unlock_error(
    recovery_code: str,
) -> RecoveryCredential:
    try:
        return parse_recovery_code(recovery_code)
    except (
        TypeError,
        ValueError,
    ):
        raise UnlockError from None


def _require_matching_header(
    container: VaultContainer,
    header: VaultHeader,
) -> None:
    if container.header != header:
        raise VaultOperationError("Vault changed during the recovery operation.")
