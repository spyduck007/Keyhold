"""Password key derivation using Argon2id."""

from __future__ import annotations

from dataclasses import dataclass

from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw

MIN_ARGON2_SALT_LENGTH = 16
PASSWORD_KEY_LENGTH = 32


@dataclass(frozen=True, slots=True)
class Argon2Parameters:
    """Versioned Argon2id parameters stored with a vault."""

    memory_cost_kib: int = 65_536
    time_cost: int = 3
    parallelism: int = 2
    output_length: int = PASSWORD_KEY_LENGTH
    version: int = ARGON2_VERSION

    def __post_init__(self) -> None:
        if self.memory_cost_kib <= 0:
            raise ValueError("memory_cost_kib must be greater than zero")

        if self.time_cost <= 0:
            raise ValueError("time_cost must be greater than zero")

        if self.parallelism <= 0:
            raise ValueError("parallelism must be greater than zero")

        if self.memory_cost_kib < 8 * self.parallelism:
            raise ValueError("memory_cost_kib must be at least 8 times parallelism")

        if self.output_length != PASSWORD_KEY_LENGTH:
            raise ValueError(f"output_length must be {PASSWORD_KEY_LENGTH} bytes")

        if self.version <= 0:
            raise ValueError("version must be greater than zero")


# These are provisional prototype parameters.
# We will benchmark and calibrate them on the target Mac later.
DEFAULT_ARGON2_PARAMETERS = Argon2Parameters()


def derive_password_key(
    password: str | bytes | bytearray | memoryview,
    salt: bytes,
    parameters: Argon2Parameters = DEFAULT_ARGON2_PARAMETERS,
) -> bytes:
    """Derive a fixed-length password key with Argon2id."""
    password_bytes = _normalize_password(password)

    if not isinstance(salt, bytes):
        raise TypeError("salt must be bytes")

    if len(salt) < MIN_ARGON2_SALT_LENGTH:
        raise ValueError(f"salt must be at least {MIN_ARGON2_SALT_LENGTH} bytes")

    return hash_secret_raw(
        secret=password_bytes,
        salt=salt,
        time_cost=parameters.time_cost,
        memory_cost=parameters.memory_cost_kib,
        parallelism=parameters.parallelism,
        hash_len=parameters.output_length,
        type=Type.ID,
        version=parameters.version,
    )


def _normalize_password(
    password: str | bytes | bytearray | memoryview,
) -> bytes:
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    elif isinstance(password, (bytes, bytearray, memoryview)):
        password_bytes = bytes(password)
    else:
        raise TypeError("password must be str or bytes-like")

    if not password_bytes:
        raise ValueError("password must not be empty")

    return password_bytes
