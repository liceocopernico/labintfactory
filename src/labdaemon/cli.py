"""Command-line tools (no GUI):

    labdaemon ports                   what is on each USB serial port
    labdaemon firmware check PORT     does the board on PORT speak the LabInt wire protocol?
"""

import argparse
import sys

from labdaemon.core.conformance import check_board
from labdaemon.core.errors import LabError
from labdaemon.core.manager import DeviceManager
from labdaemon.core.registry import Registry
from labdaemon.core.settings import Settings, plugin_dirs
from labdaemon.transports.serial import SerialTransport
from labdaemon.transports.wire import WireClient

COMMANDS = ("ports", "firmware")


def _registry() -> Registry:
    return Registry(plugin_dirs(Settings())).load()


def ports() -> int:
    manager = DeviceManager(_registry())
    results = manager.scan_serial()
    if not results:
        print("No USB serial ports found.")
        return 1
    for r in results:
        head = f"{r.port.device:<16} {r.port.usb_id:<10} {r.port.description}"
        if r.info:
            fns = ", ".join(f"{fn} ({pid or 'no plugin'})" for fn, pid in r.plugins.items())
            print(f"{head}\n{'':<16} {r.info.name} · {r.info.board} · firmware {r.info.firmware} · "
                  f"serial {r.info.serial} · {fns}")
        else:
            print(f"{head}\n{'':<16} not a LabInt board: {r.error}")
    return 0


def firmware_check(port: str) -> int:
    transport = SerialTransport(port)
    wire = WireClient(transport)
    try:
        transport.open()
        if not wire.wait_ready(3.5):
            print(f"FAIL  {port} does not answer PING")
            return 1
        info, checks = check_board(wire, _registry())
    except LabError as e:
        print(f"FAIL  {e.message}")
        return 1
    finally:
        transport.close()
    for c in checks:
        print(f"{'PASS' if c.ok else 'FAIL'}  {c.name}" + (f"  ({c.detail})" if c.detail else ""))
    failed = sum(not c.ok for c in checks)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed" + (f" on {info.name}" if info else ""))
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="labdaemon", description="LabDaemon command-line tools.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ports", help="list USB serial ports and the LabInt boards on them")
    fw = sub.add_parser("firmware", help="firmware tools").add_subparsers(dest="action", required=True)
    check = fw.add_parser("check", help="check a board against the LabInt wire protocol")
    check.add_argument("port", help="serial port, e.g. /dev/ttyACM0 or COM3")
    args = parser.parse_args(argv)
    if args.command == "ports":
        return ports()
    return firmware_check(args.port)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
