"""Simulated boards: a WireSimulator implementing the LabInt wire protocol v1, and a transport to it.

The simulator is the protocol spec in executable form. Tests run WireClient against it, device
plugins ship a simulated twin built on it, and the app can connect to it like a real board.
"""

import hashlib
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from labdaemon.core.errors import TransportError
from labdaemon.core.i18n import _
from labdaemon.core.transport import Transport
from labdaemon.transports.wire import PROTOCOL_VERSION, format_line, format_value, parse_fields, tokenize

# Standard error codes (firmware/PROTOCOL.md §5)
ERR_UNKNOWN, ERR_ARGUMENT, ERR_RANGE, ERR_BUSY, ERR_NOT_READY, ERR_HARDWARE, ERR_UNSUPPORTED, ERR_AUTH = range(1, 9)


class SimError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Busy:
    """Returned by a handler for a long command: BUSY now, `EVT DONE` after `seconds`."""

    seconds: float
    done: dict[str, Any] = field(default_factory=dict)
    stopped: Callable[[float], dict[str, Any]] | None = None  # fraction elapsed → fields of EVT STOPPED


Handler = Callable[[list[str]], dict[str, Any] | Busy | None]


class SimFunction:
    """One instrument function of a simulated board."""

    name: ClassVar[str]
    hw: ClassVar[dict[str, str]] = {}

    def attach(self, sim: WireSimulator) -> None:
        self.sim = sim

    def handlers(self) -> dict[str, Handler]:
        return {}

    def reset(self) -> None:
        pass

    def status(self) -> dict[str, Any]:
        return {}


def arg_int(args: list[str], index: int, default: int, minimum: int, maximum: int) -> int:
    if index >= len(args):
        return default
    try:
        value = int(args[index])
    except ValueError:
        raise SimError(ERR_ARGUMENT, f"argument {index} must be an integer") from None
    if not minimum <= value <= maximum:
        raise SimError(ERR_RANGE, f"value out of range {minimum}..{maximum}")
    return value


@dataclass
class _Running:
    verb: str
    started: float
    busy: Busy


class WireSimulator:
    def __init__(self, functions: Iterable[SimFunction], *, board: str = "sim", firmware: str = "0.1.0",
                 name: str | None = None, serial: str | None = None, links: tuple[str, ...] = ("usb",),
                 token: str | None = None, boot_event: bool = True, silent: bool = False) -> None:
        self.functions = {f.name: f for f in functions}
        for f in self.functions.values():
            f.attach(self)
        self.board = board
        self.firmware = firmware
        self.name = name or f"Sim-{next(iter(self.functions), 'board')}"
        self.serial = serial or hashlib.sha1(self.name.encode()).hexdigest()[:12].upper()
        self.links = links
        self.token = token
        self.boot_event = boot_event
        self.silent = silent
        self.authorised = token is None
        self._running: dict[str, _Running] = {}
        self._pending: list[str] = []  # lines to send along with the next reply (debug, events)
        self._lock = threading.Lock()

    # used by the transport
    def boot_lines(self) -> list[str]:
        self.authorised = self.token is None
        return [format_line("EVT BOOT", proto=PROTOCOL_VERSION)] if self.boot_event else []

    def handle(self, line: str) -> list[str]:
        with self._lock:
            if self.silent:
                return []
            try:
                out = self._dispatch(line)
            except SimError as e:
                out = [f"ERR {e.code} {e.message}"]
            pending, self._pending = self._pending, []
            return pending + out

    def due_lines(self, now: float) -> list[str]:
        with self._lock:
            lines = []
            for fn, run in list(self._running.items()):
                if now - run.started >= run.busy.seconds:
                    del self._running[fn]
                    lines.append(format_line("EVT DONE", fn=fn, cmd=run.verb, **run.busy.done))
            pending, self._pending = self._pending, []
            return pending + lines

    # used by simulated functions
    def debug(self, text: str) -> None:
        self._pending.append(f"# {text}")

    def event(self, name: str, **fields: Any) -> None:
        self._pending.append(format_line(f"EVT {name}", **fields))

    # protocol
    def _dispatch(self, line: str) -> list[str]:
        tokens = tokenize(line)
        if not tokens:
            raise SimError(ERR_UNKNOWN, "empty command")
        target, _sep, verb = tokens[0].rpartition(":")
        args = tokens[1:]
        if not self.authorised and verb != "AUTH":
            raise SimError(ERR_AUTH, "not authorised")
        if not target and verb in self._board_verbs():
            return self._board_verbs()[verb](args)
        fn = target or (next(iter(self.functions)) if len(self.functions) == 1 else "")
        if fn not in self.functions:
            raise SimError(ERR_UNKNOWN, f"unknown command {tokens[0]}")
        return self._function_command(fn, verb, args)

    def _function_command(self, fn: str, verb: str, args: list[str]) -> list[str]:
        if verb == "STOP":
            return [format_line("OK", fn=fn)] + self._stop([fn])
        if verb == "HW?":
            return [format_line("OK", fn=fn, **self.functions[fn].hw)]
        if fn in self._running and verb not in ("STATUS?",):
            raise SimError(ERR_BUSY, f"{fn} is busy")
        handler = self.functions[fn].handlers().get(verb)
        if handler is None:
            raise SimError(ERR_UNKNOWN, f"unknown command {verb}")
        result = handler(args)
        if isinstance(result, Busy):
            self._running[fn] = _Running(verb, time.monotonic(), result)
            return [format_line("BUSY", fn=fn)]
        return [format_line("OK", fn=fn, **(result or {}))]

    def _stop(self, fns: Iterable[str]) -> list[str]:
        lines = []
        now = time.monotonic()
        for fn in fns:
            run = self._running.pop(fn, None)
            if run:
                fraction = min(1.0, (now - run.started) / run.busy.seconds) if run.busy.seconds else 1.0
                extra = run.busy.stopped(fraction) if run.busy.stopped else {}
                lines.append(format_line("EVT STOPPED", fn=fn, cmd=run.verb, **extra))
        return lines

    def _board_verbs(self) -> dict[str, Callable[[list[str]], list[str]]]:
        return {
            "ID?": lambda a: [format_line(
                "OK", proto=PROTOCOL_VERSION, board=self.board, fw=self.firmware, serial=self.serial,
                name=self.name, functions=",".join(self.functions), links=",".join(self.links))],
            "CMDS?": lambda a: [format_line("OK", **{
                name: ",".join(["HW?", "STOP", *f.handlers()]) for name, f in self.functions.items()})],
            "PING": lambda a: ["OK"],
            "STATUS?": lambda a: [format_line("OK", **{
                name: ("busy" if name in self._running else "idle") for name in self.functions})],
            "STOP": lambda a: ["OK"] + self._stop(list(self._running)),
            "RESET": self._reset,
            "NAME": self._rename,
            "AUTH": self._auth,
        }

    def _reset(self, args: list[str]) -> list[str]:
        self._running.clear()
        for f in self.functions.values():
            f.reset()
        return ["OK"]

    def _rename(self, args: list[str]) -> list[str]:
        if not args or not args[0].strip():
            raise SimError(ERR_ARGUMENT, "name required")
        self.name = args[0][:24]
        return ["OK"]

    def _auth(self, args: list[str]) -> list[str]:
        if self.token is None or (args and args[0] == self.token):
            self.authorised = True
            return ["OK"]
        raise SimError(ERR_AUTH, "wrong token")


class SimulatedTransport(Transport):
    """An in-memory link to a WireSimulator, with optional latency."""

    kind = "simulated"

    def __init__(self, simulator: WireSimulator, *, latency: float = 0.0) -> None:
        self.simulator = simulator
        self.latency = latency
        self._open = False
        self._queue: deque[tuple[float, str]] = deque()

    @property
    def description(self) -> str:
        return _("simulated")

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True
        self._queue.clear()
        self._push(self.simulator.boot_lines())

    def close(self) -> None:
        self._open = False
        self._queue.clear()

    def write_line(self, line: str) -> None:
        if not self._open:
            raise TransportError(_("The connection to the board is closed."))
        self._push(self.simulator.handle(line))

    def read_line(self, timeout: float) -> str | None:
        if not self._open:
            raise TransportError(_("The connection to the board is closed."))
        deadline = time.monotonic() + max(timeout, 0.0)
        while True:
            now = time.monotonic()
            self._push(self.simulator.due_lines(now))
            if self._queue and self._queue[0][0] <= now:
                return self._queue.popleft()[1]
            if now >= deadline:
                return None
            time.sleep(min(0.002, deadline - now))

    def reset_input(self) -> None:
        self._queue.clear()

    def _push(self, lines: Iterable[str]) -> None:
        ready = time.monotonic() + self.latency
        self._queue.extend((ready, line) for line in lines)


__all__ = ["Busy", "SimError", "SimFunction", "SimulatedTransport", "WireSimulator", "arg_int",
           "format_value", "parse_fields"]
