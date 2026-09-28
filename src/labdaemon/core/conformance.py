"""`labdaemon firmware check`: does a board speak the LabInt wire protocol (firmware/PROTOCOL.md)?"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from labdaemon.core.board import BoardInfo
from labdaemon.core.errors import DeviceError, LabError
from labdaemon.core.registry import Registry
from labdaemon.transports.wire import FunctionChannel, WireClient


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def _run(name: str, test: Callable[[], str | None]) -> Check:
    try:
        return Check(name, True, test() or "")
    except AssertionError as e:
        return Check(name, False, str(e))
    except LabError as e:
        return Check(name, False, f"{e.message} {e.detail or ''}".strip())


def check_board(wire: WireClient, registry: Registry | None = None) -> tuple[BoardInfo | None, list[Check]]:
    checks: list[Check] = []
    info: BoardInfo | None = None

    def ping() -> str:
        t0 = time.monotonic()
        wire.query("PING")
        ms = (time.monotonic() - t0) * 1000
        assert ms < 500, f"answered in {ms:.0f} ms; the limit is 500 ms"
        return f"{ms:.0f} ms"

    checks.append(_run("PING answers within 500 ms", ping))

    def ident() -> str:
        nonlocal info
        info = wire.identify()
        return f"{info.board}, firmware {info.firmware}, serial {info.serial}, functions {','.join(info.functions)}"

    checks.append(_run("ID? reports protocol, board, serial and functions", ident))
    if info is None:
        return None, checks

    def cmds() -> str:
        reply = wire.query("CMDS?")
        missing = [fn for fn in info.functions if fn not in reply.values]
        assert not missing, f"no command list for {missing}"
        return ""

    def status() -> str:
        reply = wire.query("STATUS?")
        wrong = {fn: reply.get(fn) for fn in info.functions if reply.get(fn) not in ("idle", "busy")}
        assert not wrong, f"unexpected states {wrong}"
        return ""

    def unknown() -> str:
        try:
            wire.query("NO_SUCH_COMMAND")
        except DeviceError as e:
            assert e.code == 1, f"ERR {e.code} instead of ERR 1"
            return ""
        raise AssertionError("an unknown command was accepted")

    def stop_idle() -> str:
        assert wire.query("STOP").status == "OK"
        return ""

    checks += [_run("CMDS? lists every function", cmds), _run("STATUS? reports every function", status),
               _run("Unknown commands answer ERR 1", unknown), _run("STOP is accepted while idle", stop_idle)]

    for fn in info.functions:
        channel = FunctionChannel(wire, fn)

        def hw(channel: FunctionChannel = channel) -> str:
            reply = channel.query("HW?")
            assert reply.fn == channel.fn, "the reply lacks fn="
            return " ".join(f"{k}={v}" for k, v in reply.values.items() if k != "fn")

        checks.append(_run(f"{fn}: HW? answers", hw))
        cls = registry.device_for_model(fn) if registry else None
        if cls is None:
            checks.append(Check(f"{fn}: device plugin", False, "no installed plugin serves this function"))
        elif cls.firmware_checks is not None:
            checks += cls.firmware_checks(channel)
    return info, checks
