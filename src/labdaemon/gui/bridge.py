"""Moves core signals and futures onto the Qt GUI thread."""

from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Signal

from labdaemon.core.manager import DeviceManager


class QtBridge(QObject):
    boards_changed = Signal()
    device_state = Signal(str, str)  # device key, DeviceState value
    sample = Signal(str, object, float)  # device key, {channel: value}, monotonic time
    parameters_changed = Signal(str)  # device key
    error = Signal(str, object)  # key, LabError
    _future_done = Signal(object, object, object)

    def __init__(self, manager: DeviceManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        # Emitted from worker threads; Qt queues them to receivers living in the GUI thread.
        manager.boards_changed.connect(self.boards_changed.emit)
        manager.device_state.connect(lambda key, state: self.device_state.emit(key, str(state)))
        manager.sample.connect(self.sample.emit)
        manager.parameters_changed.connect(self.parameters_changed.emit)
        manager.error.connect(self.error.emit)
        self._future_done.connect(self._deliver)

    def watch(self, future: Future, on_ok: Callable[[Any], None] | None = None,
              on_error: Callable[[BaseException], None] | None = None) -> None:
        """Call on_ok(result) or on_error(exception) in the GUI thread when the future finishes."""
        future.add_done_callback(lambda f: self._future_done.emit(f, on_ok, on_error))

    def _deliver(self, future: Future, on_ok, on_error) -> None:
        exc = future.exception()
        if exc is None:
            if on_ok:
                on_ok(future.result())
        elif on_error:
            on_error(exc)
        else:
            logger.opt(exception=exc).error("background task failed")
