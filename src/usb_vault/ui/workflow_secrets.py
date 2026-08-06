"""Mutable text buffers for background desktop workflows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MutableTextSecret:
    """UTF-8 text held in a mutable buffer that can be overwritten."""

    _value: bytearray = field(repr=False)
    _closed: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    @classmethod
    def from_text(
        cls,
        value: str,
        *,
        allow_empty: bool = False,
    ) -> MutableTextSecret:
        """Create a mutable UTF-8 buffer from text."""
        if not isinstance(
            value,
            str,
        ):
            raise TypeError("value must be a string")

        if type(allow_empty) is not bool:
            raise TypeError("allow_empty must be a boolean")

        encoded = value.encode("utf-8")

        if not encoded and not allow_empty:
            raise ValueError("value must not be empty")

        return cls(_value=bytearray(encoded))

    @property
    def is_closed(self) -> bool:
        """Return whether the buffer was overwritten."""
        return self._closed

    def text(self) -> str:
        """Return a short-lived immutable text copy."""
        if self._closed:
            raise RuntimeError("text secret is closed")

        return bytes(self._value).decode("utf-8")

    def close(self) -> None:
        """Overwrite the mutable UTF-8 buffer."""
        if self._closed:
            return

        for index in range(len(self._value)):
            self._value[index] = 0

        self._closed = True
