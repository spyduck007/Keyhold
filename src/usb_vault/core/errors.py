"""Domain-specific exceptions used by the vault core."""

GENERIC_UNLOCK_MESSAGE = "Unable to unlock vault."


class VaultError(Exception):
    """Base class for expected vault failures."""


class UnlockError(VaultError):
    """Raised when authentication or authenticated decryption fails."""

    def __init__(self, message: str = GENERIC_UNLOCK_MESSAGE) -> None:
        super().__init__(message)


class VaultFormatError(VaultError):
    """Raised when a vault structure cannot be parsed safely."""


class VaultOperationError(VaultError):
    """Raised when a requested vault operation cannot be completed."""


class EntryExistsError(VaultOperationError):
    """Raised when a vault entry already uses the requested name."""


class EntryNotFoundError(VaultOperationError):
    """Raised when a requested vault entry does not exist."""


class KeySlotNotFoundError(VaultOperationError):
    """Raised when a requested USB key slot is not registered."""


class LastKeySlotError(VaultOperationError):
    """Raised when an operation would remove the final USB key slot."""


class CurrentKeyRevocationError(VaultOperationError):
    """Raised when attempting to revoke the key used for the session."""
