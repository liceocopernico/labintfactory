"""One worker thread per connection (a board, or a Vernier sensor).

The worker is the only thread that ever touches its board's transport and devices. Everyone else
submits jobs: the GUI with submit() (returns a Future at once), experiment runners and notebooks
with call() or through a DeviceProxy (blocks the *caller* until the result is ready).
"""

import itertools
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from labdaemon.core.events import Signal

_URGENT, _NORMAL, _STOP = 0, 1, 2


@dataclass(order=True)
class _Job:
    priority: int
    seq: int
    fn: Callable[..., Any] | None = field(compare=False)
    args: tuple = field(compare=False, default=())
    kwargs: dict = field(compare=False, default_factory=dict)
    future: Future = field(compare=False, default_factory=Future)


@dataclass
class _Poll:
    fn: Callable[[], Any]
    interval: float
    due: float


class BoardWorker:
    def __init__(self, name: str, *, idle: Callable[[float], Any] | None = None) -> None:
        """`idle(timeout)` is called when nothing is queued; the board uses it to read incoming events."""
        self.name = name
        self._idle = idle
        self._jobs: queue.PriorityQueue[_Job] = queue.PriorityQueue()
        self._seq = itertools.count()
        self._polls: dict[str, _Poll] = {}
        self._thread = threading.Thread(target=self._loop, name=f"board-{name}", daemon=True)
        self._stopping = False
        self.polled = Signal("worker.polled")  # (key, result, monotonic time)
        self.poll_failed = Signal("worker.poll_failed")  # (key, exception)

    def start(self) -> None:
        self._thread.start()

    @property
    def running(self) -> bool:
        return self._thread.is_alive() and not self._stopping

    def in_worker(self) -> bool:
        return threading.current_thread() is self._thread

    def submit(self, fn: Callable[..., Any], /, *args: Any, urgent: bool = False, **kwargs: Any) -> Future:
        """Queue fn(*args, **kwargs); urgent jobs (STOP) go before everything already queued."""
        job = _Job(_URGENT if urgent else _NORMAL, next(self._seq), fn, args, kwargs)
        if self._stopping:
            job.future.set_exception(RuntimeError(f"worker {self.name} is stopped"))
        else:
            self._jobs.put(job)
        return job.future

    def call(self, fn: Callable[..., Any], /, *args: Any, timeout: float | None = None, **kwargs: Any) -> Any:
        """Run fn on the worker and wait for its result. Never call this from the GUI thread."""
        if self.in_worker():
            return fn(*args, **kwargs)
        return self.submit(fn, *args, **kwargs).result(timeout)

    def add_poll(self, key: str, fn: Callable[[], Any], interval: float) -> None:
        def install() -> None:
            self._polls[key] = _Poll(fn, interval, time.monotonic())

        self.submit(install)

    def remove_poll(self, key: str) -> None:
        self.submit(lambda: self._polls.pop(key, None))

    def shutdown(self, timeout: float = 3.0) -> None:
        if not self._thread.is_alive():
            return
        self._stopping = True
        self._jobs.put(_Job(_STOP, next(self._seq), None))
        if not self.in_worker():
            self._thread.join(timeout)

    def _loop(self) -> None:
        while True:
            now = time.monotonic()
            wait = min((p.due for p in self._polls.values()), default=now + 0.05) - now
            try:
                job = self._jobs.get(timeout=max(0.0, min(wait, 0.05)))
            except queue.Empty:
                job = None
            if job is not None:
                if job.fn is None:
                    break
                self._execute(job)
            elif self._idle is not None:
                try:
                    self._idle(0.0)
                except Exception as e:
                    logger.warning("{}: while idle: {}", self.name, e)
            self._run_due_polls()
        # refuse whatever is still queued
        while not self._jobs.empty():
            left = self._jobs.get_nowait()
            if left.fn is not None and not left.future.done():
                left.future.set_exception(RuntimeError(f"worker {self.name} stopped"))

    def _execute(self, job: _Job) -> None:
        if not job.future.set_running_or_notify_cancel():
            return
        try:
            job.future.set_result(job.fn(*job.args, **job.kwargs))
        except BaseException as e:  # delivered to whoever waits on the future
            job.future.set_exception(e)

    def _run_due_polls(self) -> None:
        now = time.monotonic()
        for key, poll in list(self._polls.items()):
            if poll.due > now:
                continue
            poll.due = max(poll.due + poll.interval, now)  # no burst after a long job
            try:
                result = poll.fn()
            except Exception as e:
                self.poll_failed.emit(key, e)
            else:
                self.polled.emit(key, result, time.monotonic())


class DeviceProxy:
    """Looks like the device, but every method call runs on the board's worker and waits for it.

    Used by experiment code and notebooks, never by the GUI thread (which uses submit()).
    If a method returns an Operation (a long command such as a move), the proxy waits for it too.
    """

    def __init__(self, worker: BoardWorker, device: Any) -> None:
        object.__setattr__(self, "_worker", worker)
        object.__setattr__(self, "_device", device)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._device, name)
        if not callable(attr):
            return attr

        def call(*args: Any, **kwargs: Any) -> Any:
            result = self._worker.call(attr, *args, **kwargs)
            from labdaemon.transports.wire import Operation

            if isinstance(result, Operation):
                return result.wait()
            return result

        call.__name__ = name
        call.__doc__ = getattr(attr, "__doc__", None)
        return call

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("devices are changed through their methods, e.g. set_parameter()")

    def __dir__(self) -> list[str]:
        return [n for n in dir(self._device) if not n.startswith("_")]

    def __repr__(self) -> str:
        return f"<proxy of {self._device.display_name}>"
