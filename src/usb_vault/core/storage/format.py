"""Versioned serialized vault-header formats."""

from __future__ import annotations

from dataclasses import dataclass

from usb_vault.core.crypto.encryption import (
    AES_GCM_TAG_LENGTH,
    WrappedMasterKey,
)
from usb_vault.core.crypto.password_kdf import (
    Argon2Parameters,
)
from usb_vault.core.crypto.random import (
    AES_GCM_NONCE_LENGTH,
    ARGON2_SALT_LENGTH,
    MASTER_KEY_LENGTH,
    secure_random_bytes,
)
from usb_vault.core.errors import (
    VaultFormatError,
)
from usb_vault.core.keys.keyfile import (
    KEY_ID_LENGTH,
)
from usb_vault.core.keys.recovery import (
    RECOVERY_ID_LENGTH,
)
from usb_vault.core.serialization import (
    canonical_json_bytes,
    decode_base64,
    encode_base64,
    parse_json_object,
    require_exact_keys,
    require_integer,
    require_list,
    require_object,
    require_string,
)

VAULT_MAGIC = "USBVAULT"
LEGACY_VAULT_FORMAT_VERSION = 1
VAULT_FORMAT_VERSION = 2
VAULT_ID_LENGTH = 16

KDF_IDENTIFIER = "argon2id"
VAULT_CIPHER_IDENTIFIER = "aes-256-gcm"
PASSWORD_USB_SLOT_TYPE = "password_usb"
KEY_SLOT_TYPE = PASSWORD_USB_SLOT_TYPE
RECOVERY_SLOT_TYPE = "password_recovery"
WRAP_CIPHER_IDENTIFIER = "aes-256-gcm"

WRAPPED_MASTER_KEY_LENGTH = MASTER_KEY_LENGTH + AES_GCM_TAG_LENGTH

INVALID_VAULT_HEADER_MESSAGE = "Invalid vault header."

_LEGACY_HEADER_FIELDS = {
    "magic",
    "version",
    "vault_id",
    "kdf",
    "vault_cipher",
    "key_slots",
}

_HEADER_FIELDS = {
    *_LEGACY_HEADER_FIELDS,
    "recovery_slots",
}

_KDF_FIELDS = {
    "name",
    "salt",
    "memory_cost_kib",
    "time_cost",
    "parallelism",
    "output_length",
    "version",
}

_PASSWORD_USB_SLOT_FIELDS = {
    "slot_type",
    "key_id",
    "wrap_cipher",
    "nonce",
    "wrapped_master_key",
}

_RECOVERY_SLOT_FIELDS = {
    "slot_type",
    "recovery_id",
    "wrap_cipher",
    "nonce",
    "wrapped_master_key",
}


@dataclass(frozen=True, slots=True)
class PasswordUsbKeySlot:
    """One password-plus-USB master-key slot."""

    key_id: bytes
    wrapped_master_key: WrappedMasterKey
    slot_type: str = PASSWORD_USB_SLOT_TYPE
    wrap_cipher: str = WRAP_CIPHER_IDENTIFIER

    def __post_init__(self) -> None:
        _require_bytes_length(
            "key_id",
            self.key_id,
            KEY_ID_LENGTH,
        )
        _validate_wrapped_master_key(self.wrapped_master_key)

        if self.slot_type != PASSWORD_USB_SLOT_TYPE:
            raise ValueError(f"unsupported key-slot type: {self.slot_type}")

        if self.wrap_cipher != WRAP_CIPHER_IDENTIFIER:
            raise ValueError(f"unsupported wrap cipher: {self.wrap_cipher}")

    def to_object(
        self,
    ) -> dict[str, object]:
        """Return the USB slot's JSON representation."""
        return {
            "slot_type": self.slot_type,
            "key_id": encode_base64(self.key_id),
            "wrap_cipher": self.wrap_cipher,
            "nonce": encode_base64(self.wrapped_master_key.nonce),
            "wrapped_master_key": encode_base64(self.wrapped_master_key.ciphertext),
        }

    @classmethod
    def from_object(
        cls,
        value: object,
    ) -> PasswordUsbKeySlot:
        """Parse one password-plus-USB slot."""
        payload = require_object(
            value,
            field_name="key slot",
        )

        require_exact_keys(
            payload,
            _PASSWORD_USB_SLOT_FIELDS,
            object_name="key slot",
        )

        slot_type = require_string(
            payload["slot_type"],
            field_name="slot_type",
        )
        wrap_cipher = require_string(
            payload["wrap_cipher"],
            field_name="wrap_cipher",
        )

        if slot_type != PASSWORD_USB_SLOT_TYPE:
            raise ValueError("unsupported key-slot type")

        if wrap_cipher != WRAP_CIPHER_IDENTIFIER:
            raise ValueError("unsupported wrap cipher")

        return cls(
            key_id=decode_base64(
                payload["key_id"],
                field_name="key_id",
            ),
            wrapped_master_key=(_parse_wrapped_master_key(payload)),
            slot_type=slot_type,
            wrap_cipher=wrap_cipher,
        )


@dataclass(frozen=True, slots=True)
class RecoveryKeySlot:
    """One password-plus-recovery-code master-key slot."""

    recovery_id: bytes
    wrapped_master_key: WrappedMasterKey
    slot_type: str = RECOVERY_SLOT_TYPE
    wrap_cipher: str = WRAP_CIPHER_IDENTIFIER

    def __post_init__(self) -> None:
        _require_bytes_length(
            "recovery_id",
            self.recovery_id,
            RECOVERY_ID_LENGTH,
        )
        _validate_wrapped_master_key(self.wrapped_master_key)

        if self.slot_type != RECOVERY_SLOT_TYPE:
            raise ValueError(f"unsupported recovery-slot type: {self.slot_type}")

        if self.wrap_cipher != WRAP_CIPHER_IDENTIFIER:
            raise ValueError(f"unsupported wrap cipher: {self.wrap_cipher}")

    def to_object(
        self,
    ) -> dict[str, object]:
        """Return the recovery slot's JSON representation."""
        return {
            "slot_type": self.slot_type,
            "recovery_id": encode_base64(self.recovery_id),
            "wrap_cipher": self.wrap_cipher,
            "nonce": encode_base64(self.wrapped_master_key.nonce),
            "wrapped_master_key": encode_base64(self.wrapped_master_key.ciphertext),
        }

    @classmethod
    def from_object(
        cls,
        value: object,
    ) -> RecoveryKeySlot:
        """Parse one password-plus-recovery-code slot."""
        payload = require_object(
            value,
            field_name="recovery slot",
        )

        require_exact_keys(
            payload,
            _RECOVERY_SLOT_FIELDS,
            object_name="recovery slot",
        )

        slot_type = require_string(
            payload["slot_type"],
            field_name="slot_type",
        )
        wrap_cipher = require_string(
            payload["wrap_cipher"],
            field_name="wrap_cipher",
        )

        if slot_type != RECOVERY_SLOT_TYPE:
            raise ValueError("unsupported recovery-slot type")

        if wrap_cipher != WRAP_CIPHER_IDENTIFIER:
            raise ValueError("unsupported wrap cipher")

        return cls(
            recovery_id=decode_base64(
                payload["recovery_id"],
                field_name="recovery_id",
            ),
            wrapped_master_key=(_parse_wrapped_master_key(payload)),
            slot_type=slot_type,
            wrap_cipher=wrap_cipher,
        )


@dataclass(frozen=True, slots=True)
class VaultHeader:
    """The versioned header needed to attempt vault unlock."""

    vault_id: bytes
    argon2_salt: bytes
    argon2_parameters: Argon2Parameters
    key_slots: tuple[
        PasswordUsbKeySlot,
        ...,
    ]
    recovery_slots: tuple[
        RecoveryKeySlot,
        ...,
    ] = ()
    version: int = VAULT_FORMAT_VERSION
    vault_cipher: str = VAULT_CIPHER_IDENTIFIER

    def __post_init__(self) -> None:
        _require_bytes_length(
            "vault_id",
            self.vault_id,
            VAULT_ID_LENGTH,
        )
        _require_bytes_length(
            "argon2_salt",
            self.argon2_salt,
            ARGON2_SALT_LENGTH,
        )

        if not isinstance(
            self.argon2_parameters,
            Argon2Parameters,
        ):
            raise TypeError("argon2_parameters must be Argon2Parameters")

        if not isinstance(
            self.key_slots,
            tuple,
        ):
            raise TypeError("key_slots must be a tuple")

        if not self.key_slots:
            raise ValueError("vault header must contain at least one key slot")

        if not all(
            isinstance(
                slot,
                PasswordUsbKeySlot,
            )
            for slot in self.key_slots
        ):
            raise TypeError("every key slot must be PasswordUsbKeySlot")

        if not isinstance(
            self.recovery_slots,
            tuple,
        ):
            raise TypeError("recovery_slots must be a tuple")

        if not all(
            isinstance(
                slot,
                RecoveryKeySlot,
            )
            for slot in self.recovery_slots
        ):
            raise TypeError("every recovery slot must be RecoveryKeySlot")

        key_ids = [slot.key_id for slot in self.key_slots]
        recovery_ids = [slot.recovery_id for slot in self.recovery_slots]

        if len(key_ids) != len(set(key_ids)):
            raise ValueError("key-slot identifiers must be unique")

        if len(recovery_ids) != len(set(recovery_ids)):
            raise ValueError("recovery-slot identifiers must be unique")

        if self.version not in {
            LEGACY_VAULT_FORMAT_VERSION,
            VAULT_FORMAT_VERSION,
        }:
            raise ValueError(f"unsupported vault version: {self.version}")

        if self.version == LEGACY_VAULT_FORMAT_VERSION and self.recovery_slots:
            raise ValueError("legacy headers cannot contain recovery slots")

        if self.vault_cipher != VAULT_CIPHER_IDENTIFIER:
            raise ValueError(f"unsupported vault cipher: {self.vault_cipher}")

    def to_bytes(self) -> bytes:
        """Serialize the header deterministically."""
        parameters = self.argon2_parameters

        kdf_object: dict[str, object] = {
            "name": KDF_IDENTIFIER,
            "salt": encode_base64(self.argon2_salt),
            "memory_cost_kib": (parameters.memory_cost_kib),
            "time_cost": (parameters.time_cost),
            "parallelism": (parameters.parallelism),
            "output_length": (parameters.output_length),
            "version": parameters.version,
        }

        payload: dict[str, object] = {
            "magic": VAULT_MAGIC,
            "version": self.version,
            "vault_id": encode_base64(self.vault_id),
            "kdf": kdf_object,
            "vault_cipher": (self.vault_cipher),
            "key_slots": [slot.to_object() for slot in self.key_slots],
        }

        if self.version == VAULT_FORMAT_VERSION:
            payload["recovery_slots"] = [slot.to_object() for slot in (self.recovery_slots)]

        return canonical_json_bytes(payload)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
    ) -> VaultHeader:
        """Parse supported vault-header versions."""
        try:
            payload = parse_json_object(data)

            magic = require_string(
                payload.get("magic"),
                field_name="magic",
            )
            version = require_integer(
                payload.get("version"),
                field_name="version",
            )

            if magic != VAULT_MAGIC:
                raise ValueError("invalid vault magic")

            if version == LEGACY_VAULT_FORMAT_VERSION:
                require_exact_keys(
                    payload,
                    _LEGACY_HEADER_FIELDS,
                    object_name="vault header",
                )
                raw_recovery_slots: list[object] = []
            elif version == VAULT_FORMAT_VERSION:
                require_exact_keys(
                    payload,
                    _HEADER_FIELDS,
                    object_name="vault header",
                )
                raw_recovery_slots = require_list(
                    payload["recovery_slots"],
                    field_name=("recovery_slots"),
                )
            else:
                raise ValueError("unsupported vault version")

            vault_cipher = require_string(
                payload["vault_cipher"],
                field_name="vault_cipher",
            )

            if vault_cipher != VAULT_CIPHER_IDENTIFIER:
                raise ValueError("unsupported vault cipher")

            kdf = require_object(
                payload["kdf"],
                field_name="kdf",
            )

            require_exact_keys(
                kdf,
                _KDF_FIELDS,
                object_name="kdf",
            )

            kdf_name = require_string(
                kdf["name"],
                field_name="kdf.name",
            )

            if kdf_name != KDF_IDENTIFIER:
                raise ValueError("unsupported password KDF")

            parameters = Argon2Parameters(
                memory_cost_kib=require_integer(
                    kdf["memory_cost_kib"],
                    field_name=("kdf.memory_cost_kib"),
                ),
                time_cost=require_integer(
                    kdf["time_cost"],
                    field_name=("kdf.time_cost"),
                ),
                parallelism=require_integer(
                    kdf["parallelism"],
                    field_name=("kdf.parallelism"),
                ),
                output_length=require_integer(
                    kdf["output_length"],
                    field_name=("kdf.output_length"),
                ),
                version=require_integer(
                    kdf["version"],
                    field_name=("kdf.version"),
                ),
            )

            raw_slots = require_list(
                payload["key_slots"],
                field_name="key_slots",
            )

            return cls(
                vault_id=decode_base64(
                    payload["vault_id"],
                    field_name="vault_id",
                ),
                argon2_salt=decode_base64(
                    kdf["salt"],
                    field_name="kdf.salt",
                ),
                argon2_parameters=parameters,
                key_slots=tuple(PasswordUsbKeySlot.from_object(slot) for slot in raw_slots),
                recovery_slots=tuple(
                    RecoveryKeySlot.from_object(slot) for slot in (raw_recovery_slots)
                ),
                version=version,
                vault_cipher=vault_cipher,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            raise VaultFormatError(INVALID_VAULT_HEADER_MESSAGE) from None

    def find_password_usb_slot(
        self,
        key_id: bytes,
    ) -> PasswordUsbKeySlot | None:
        """Find a slot using its USB key ID."""
        _require_bytes_length(
            "key_id",
            key_id,
            KEY_ID_LENGTH,
        )

        for slot in self.key_slots:
            if slot.key_id == key_id:
                return slot

        return None

    def find_recovery_slot(
        self,
        recovery_id: bytes,
    ) -> RecoveryKeySlot | None:
        """Find a slot using its recovery ID."""
        _require_bytes_length(
            "recovery_id",
            recovery_id,
            RECOVERY_ID_LENGTH,
        )

        for slot in self.recovery_slots:
            if slot.recovery_id == recovery_id:
                return slot

        return None


def create_initial_vault_header(
    *,
    argon2_salt: bytes,
    argon2_parameters: Argon2Parameters,
    key_id: bytes,
    wrapped_master_key: WrappedMasterKey,
) -> VaultHeader:
    """Create a current header with its first USB slot."""
    return VaultHeader(
        vault_id=secure_random_bytes(VAULT_ID_LENGTH),
        argon2_salt=argon2_salt,
        argon2_parameters=(argon2_parameters),
        key_slots=(
            PasswordUsbKeySlot(
                key_id=key_id,
                wrapped_master_key=(wrapped_master_key),
            ),
        ),
    )


def _parse_wrapped_master_key(
    payload: dict[str, object],
) -> WrappedMasterKey:
    return WrappedMasterKey(
        nonce=decode_base64(
            payload["nonce"],
            field_name="nonce",
        ),
        ciphertext=decode_base64(
            payload["wrapped_master_key"],
            field_name="wrapped_master_key",
        ),
    )


def _validate_wrapped_master_key(
    wrapped_master_key: WrappedMasterKey,
) -> None:
    if not isinstance(
        wrapped_master_key,
        WrappedMasterKey,
    ):
        raise TypeError("wrapped_master_key must be WrappedMasterKey")

    _require_bytes_length(
        "wrapped master key nonce",
        wrapped_master_key.nonce,
        AES_GCM_NONCE_LENGTH,
    )
    _require_bytes_length(
        "wrapped master key ciphertext",
        wrapped_master_key.ciphertext,
        WRAPPED_MASTER_KEY_LENGTH,
    )


def _require_bytes_length(
    name: str,
    value: bytes,
    expected_length: int,
) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")

    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")
