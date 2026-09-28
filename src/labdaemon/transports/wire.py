"""PC side of the LabInt wire protocol, version 1 (firmware/PROTOCOL.md).

A WireClient belongs to one board and is used only from that board's worker thread.
"""

import builtins
import math
import time
from collections.abc import Iterable
from concurrent.futures import Future
from dataclasses import dataclass, field

from loguru import logger

from labdaemon.core.board import BoardInfo
from labdaemon.core.errors import (
    BadReply,
    DeviceError,
    Interrupted,
    LimitReached,
    ProtocolTimeout,
    UnsupportedProtocol,
)
from labdaemon.core.events import Signal
from labdaemon.core.i18n import _
from labdaemon.core.transport import Transport

PROTOCOL_VERSION = 1
SUPPORTED_PROTOCOLS = (PROTOCOL_VERSION,)  # the current and, from version 2 on, the previous one
REPLY_TIMEOUT = 0.5  # the spec: a command answers within 500 ms, or with BUSY
TERMINAL_EVENTS = ("DONE", "STOPPED", "LIMIT", "FAULT")


# ── line format ─────────────────────────────────────────────────────────────────────────────────

def tokenize(line: str) -> list[str]:
    """Split on spaces; double quotes group (also inside key="a value"); \\" and \\\\ escape in quotes."""
    tokens: list[str] = []
    current: list[str] = []
    in_token = in_quotes = False
    chars = iter(line)
    for ch in chars:
        if in_quotes:
            if ch == "\\":
                current.append(next(chars, ""))
            elif ch == '"':
                in_quotes = False
            else:
                current.append(ch)
        elif ch == '"':
            in_quotes = in_token = True
        elif ch in " \t":
            if in_token:
                tokens.append("".join(current))
                current, in_token = [], False
        else:
            current.append(ch)
            in_token = True
    if in_quotes:
        raise BadReply(_("Malformed line from the board (unbalanced quotes)."), detail=line)
    if in_token:
        tokens.append("".join(current))
    return tokens


def format_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"cannot send {value!r}")
        text = repr(value)  # always '.', whatever the locale
        return text[:-2] if text.endswith(".0") else text
    text = str(value)
    if not text or any(c in text for c in ' \t"\\'):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def format_line(verb: str, *args: object, **fields: object) -> str:
    parts = [verb, *(format_value(a) for a in args)]
    parts += [f"{k}={format_value(v)}" for k, v in fields.items()]
    return " ".join(parts)


def parse_fields(tokens: Iterable[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if sep and key:
            values[key] = value
        else:
            values.setdefault("_", token)  # a bare word; kept for diagnostics only
    return values


# ── messages ────────────────────────────────────────────────────────────────────────────────────

_MISSING = object()


@dataclass(frozen=True)
class Fields:
    values: dict[str, str] = field(default_factory=dict)

    def __contains__(self, key: str) -> bool:
        return key in self.values

    def get(self, key: str, default: builtins.str | None = None) -> builtins.str | None:
        return self.values.get(key, default)

    def str(self, key: builtins.str, default: object = _MISSING) -> builtins.str:
        if key in self.values:
            return self.values[key]
        if default is _MISSING:
            raise BadReply(_("The board's reply lacks {key!r}.").format(key=key), detail=repr(self.values))
        return builtins.str(default)

    def int(self, key: builtins.str, default: object = _MISSING) -> builtins.int:
        return self._convert(key, builtins.int, default)

    def float(self, key: builtins.str, default: object = _MISSING) -> builtins.float:
        return self._convert(key, builtins.float, default)

    def bool(self, key: builtins.str, default: object = _MISSING) -> builtins.bool:
        return self._convert(key, lambda v: v not in ("0", "false", "no", "off", ""), default)

    def _convert(self, key, conv, default):
        if key not in self.values:
            if default is _MISSING:
                raise BadReply(_("The board's reply lacks {key!r}.").format(key=key), detail=repr(self.values))
            return default
        try:
            return conv(self.values[key])
        except ValueError:
            raise BadReply(_("The board sent an invalid value for {key!r}.").format(key=key),
                           detail=repr(self.values)) from None


@dataclass(frozen=True)
class Reply(Fields):
    status: builtins.str = "OK"  # "OK" | "BUSY"

    @property
    def fn(self) -> builtins.str | None:
        return self.values.get("fn")


@dataclass(frozen=True)
class Event(Fields):
    name: builtins.str = ""

    @property
    def fn(self) -> builtins.str | None:
        return self.values.get("fn")


class Operation:
    """A long command answered with BUSY; completed by its DONE / STOPPED / LIMIT / FAULT event."""

    def __init__(self, fn: str | None, verb: str) -> None:
        self.fn = fn
        self.verb = verb
        self._future: Future[Event] = Future()

    def done(self) -> bool:
        return self._future.done()

    def event(self, timeout: float | None = None) -> Event:
        """The raw final event (whatever it is)."""
        return self._future.result(timeout)

    def wait(self, timeout: float | None = None) -> Event:
        """The DONE event, or the matching exception for STOPPED, LIMIT and FAULT."""
        ev = self.event(timeout)
        if ev.name == "DONE":
            return ev
        message = ev.get("msg") or ev.name.lower()
        if ev.name == "STOPPED":
            raise Interrupted(0, _("Stopped."), detail=repr(ev.values))
        if ev.name == "LIMIT":
            raise LimitReached(0, _("A limit was reached."), detail=repr(ev.values))
        raise DeviceError(ev.int("code", 6), message, detail=repr(ev.values))

    def _finish(self, ev: Event) -> None:
        if not self._future.done():
            self._future.set_result(ev)

    def _fail(self, exc: BaseException) -> None:
        if not self._future.done():
            self._future.set_exception(exc)


# ── client ──────────────────────────────────────────────────────────────────────────────────────

class WireClient:
    def __init__(self, transport: Transport, *, name: str = "") -> None:
        self.transport = transport
        self.name = name or transport.description
        self.events = Signal("wire.events")  # (Event)
        self.debug = Signal("wire.debug")  # (text) — "#" lines from the firmware
        self._operations: dict[str | None, Operation] = {}

    # commands
    def query(self, verb: str, *args: object, fn: str | None = None, timeout: float = REPLY_TIMEOUT) -> Reply:
        line = format_line(f"{fn}:{verb}" if fn else verb, *args)
        self.transport.write_line(line)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProtocolTimeout(
                    _("{board} did not answer in time.").format(board=self.name), detail=line)
            raw = self.transport.read_line(remaining)
            if raw is None:
                continue
            result = self._handle(raw)
            if isinstance(result, DeviceError):
                result.detail = line
                raise result
            if isinstance(result, Reply):
                return result

    def start(self, verb: str, *args: object, fn: str | None = None,
              timeout: float = REPLY_TIMEOUT) -> Operation:
        """Send a long command. Returns at once; the Operation completes when its event arrives."""
        op = Operation(fn, verb)
        reply = self.query(verb, *args, fn=fn, timeout=timeout)
        if reply.status == "BUSY":
            self._operations[reply.fn or fn] = op
        else:  # finished straight away: complete it with its own reply
            op._finish(Event(values=dict(reply.values), name="DONE"))
        return op

    def run(self, verb: str, *args: object, fn: str | None = None, timeout: float = 5.0) -> Fields:
        """Send a command that may answer OK at once or BUSY then DONE; wait here for the result.

        For short measurements only: it keeps the board's worker busy until the result arrives.
        """
        op = self.start(verb, *args, fn=fn)
        deadline = time.monotonic() + timeout
        while not op.done():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProtocolTimeout(_("{board} did not finish {verb} in time.").format(
                    board=self.name, verb=verb))
            self.pump(min(remaining, 0.05))
        return op.wait(0)

    # incoming lines
    def pump(self, timeout: float = 0.0) -> int:
        """Handle lines that arrived on their own (events, debug). Returns how many were handled."""
        handled = 0
        wait = timeout
        while (raw := self.transport.read_line(wait)) is not None:
            wait = 0.0
            result = self._handle(raw)
            if isinstance(result, (Reply, DeviceError)):
                # A reply nobody is waiting for: most likely the late answer to a timed-out command.
                logger.warning("{}: unexpected reply ignored: {}", self.name, raw)
            handled += 1
        return handled

    def wait_event(self, names: Iterable[str], timeout: float) -> Event | None:
        wanted = set(names)
        got: list[Event] = []
        grab = got.append

        def listener(ev: Event) -> None:
            if ev.name in wanted:
                grab(ev)

        self.events.connect(listener)
        try:
            deadline = time.monotonic() + timeout
            while not got and (remaining := deadline - time.monotonic()) > 0:
                self.pump(min(remaining, 0.05))
        finally:
            self.events.disconnect(listener)
        return got[0] if got else None

    def wait_boot(self, timeout: float = 3.0) -> bool:
        """Boards that reset when the port opens say EVT BOOT; wait for it instead of sleeping blindly."""
        return self.wait_event(["BOOT"], timeout) is not None

    def wait_ready(self, timeout: float = 3.5) -> bool:
        """Wait until the board answers PING.

        Boards that reset when the port opens (classic Arduino) say EVT BOOT once they are up; boards
        with native USB (UNO R4, ESP32-S3 …) don't reset and answer at once. So: PING right away, and if
        there is no answer, keep listening for BOOT and PING again.
        """
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                self.query("PING", timeout=min(0.4, remaining))
                return True
            except ProtocolTimeout:
                pass
            except (DeviceError, BadReply):
                # something answered, but not yet sensibly (boot noise): drop it and try again
                self.transport.reset_input()
            self.wait_event(["BOOT"], min(1.0, max(0.0, deadline - time.monotonic())))
        return False

    def identify(self) -> BoardInfo:
        info = BoardInfo.from_fields(self.query("ID?", timeout=1.0).values)
        if info.proto not in SUPPORTED_PROTOCOLS:
            raise UnsupportedProtocol(
                _("{board} speaks protocol version {version}; this LabDaemon supports {supported}.").format(
                    board=info.name, version=info.proto,
                    supported=", ".join(map(str, SUPPORTED_PROTOCOLS))))
        return info

    def function(self, fn: str) -> FunctionChannel:
        return FunctionChannel(self, fn)

    def fail_pending(self, exc: BaseException) -> None:
        for op in self._operations.values():
            op._fail(exc)
        self._operations.clear()

    def _handle(self, raw: str) -> Reply | DeviceError | None:
        line = raw.strip()
        if not line:
            return None
        if line.startswith("#"):
            self.debug.emit(line[1:].strip())
            return None
        tokens = tokenize(line)
        head = tokens[0]
        if head in ("OK", "BUSY"):
            return Reply(values=parse_fields(tokens[1:]), status=head)
        if head == "ERR":
            try:
                code = int(tokens[1])
            except (IndexError, ValueError):
                raise BadReply(_("Malformed error reply from the board."), detail=line) from None
            return DeviceError(code, " ".join(tokens[2:]) or _("error {code}").format(code=code))
        if head == "EVT" and len(tokens) >= 2:
            ev = Event(values=parse_fields(tokens[2:]), name=tokens[1])
            if ev.name in TERMINAL_EVENTS:
                op = self._operations.pop(ev.fn, None) or self._operations.pop(None, None)
                if op:
                    op._finish(ev)
            self.events.emit(ev)
            return None
        raise BadReply(_("Unexpected line from the board."), detail=line)


class FunctionChannel:
    """What a device plugin gets: the board's client, with every command addressed to one function."""

    def __init__(self, client: WireClient, fn: str) -> None:
        self.client = client
        self.fn = fn

    def query(self, verb: str, *args: object, timeout: float = REPLY_TIMEOUT) -> Reply:
        return self.client.query(verb, *args, fn=self.fn, timeout=timeout)

    def start(self, verb: str, *args: object, timeout: float = REPLY_TIMEOUT) -> Operation:
        return self.client.start(verb, *args, fn=self.fn, timeout=timeout)

    def run(self, verb: str, *args: object, timeout: float = 5.0) -> Fields:
        return self.client.run(verb, *args, fn=self.fn, timeout=timeout)

