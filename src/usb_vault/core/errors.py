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
