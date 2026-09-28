"""A small thread-safe observer, used everywhere the core reports something happening."""

import threading
from collections.abc import Callable
from typing import Any

from loguru import logger


class Signal:
    """Callbacks run in the thread that calls emit(); the GUI bridge moves them to the Qt thread."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._slots: list[Callable[..., Any]] = []
        self._lock = threading.Lock()

    def connect[F: Callable[..., Any]](self, slot: F) -> F:
        with self._lock:
            self._slots.append(slot)
        return slot

    def disconnect(self, slot: Callable[..., Any]) -> None:
        with self._lock:
            if slot in self._slots:
                self._slots.remove(slot)

    def emit(self, *args: Any) -> None:
        with self._lock:
            slots = list(self._slots)
        for slot in slots:
            try:
                slot(*args)
            except Exception:
                # One broken listener must not stop the others, or the worker thread that emitted.
                logger.exception("listener of signal {!r} failed", self.name)

    def __len__(self) -> int:
        return len(self._slots)
