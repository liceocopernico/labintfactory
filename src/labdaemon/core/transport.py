"""Transports move lines of text between the PC and a board (serial, TCP, Bluetooth, simulated)."""

from abc import ABC, abstractmethod
from typing import ClassVar


class Transport(ABC):
    kind: ClassVar[str]  # "serial" | "tcp" | "ble" | "simulated"

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def write_line(self, line: str) -> None:
        """Send one line; the transport adds the terminator."""

    @abstractmethod
    def read_line(self, timeout: float) -> str | None:
        """Return the next line without its terminator, or None if nothing arrived within `timeout` s."""

    def reset_input(self) -> None:
        """Discard anything received but not read yet."""

    @property
    def description(self) -> str:
        return self.kind
