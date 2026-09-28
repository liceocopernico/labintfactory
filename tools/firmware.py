"""Build and upload the reference firmware with arduino-cli (the copy inside Arduino IDE 2 is fine).

    uv run python tools/firmware.py build photometer
    uv run python tools/firmware.py upload photometer --port /dev/ttyACM0   # then runs `labdaemon firmware check`

Set ARDUINO_CLI to use a specific arduino-cli.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "firmware" / "lib" / "LabInt"
SKETCHES = ROOT / "firmware" / "sketches"
BOARDS = {"photometer": "arduino:renesas_uno:minima"}  # sketch → default board (FQBN)

_IN_IDE = "resources/app/lib/backend/resources"  # where Arduino IDE 2 keeps its arduino-cli
IDE_LOCATIONS = [
    Path("/opt/arduino-ide") / _IN_IDE / "arduino-cli",
    Path.home() / "Applications/arduino-ide" / _IN_IDE / "arduino-cli",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Arduino IDE" / _IN_IDE / "arduino-cli.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Arduino IDE" / _IN_IDE / "arduino-cli.exe",
]


def arduino_cli() -> str:
    for candidate in [os.environ.get("ARDUINO_CLI"), shutil.which("arduino-cli"), *map(str, IDE_LOCATIONS)]:
        if candidate and Path(candidate).is_file():
            return candidate
    sys.exit("arduino-cli not found: install Arduino IDE 2 or arduino-cli, or set ARDUINO_CLI")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["build", "upload"])
    parser.add_argument("sketch", choices=sorted(BOARDS))
    parser.add_argument("--board", help="FQBN (default: the sketch's reference board)")
    parser.add_argument("--port", help="serial port for upload")
    args = parser.parse_args()
    fqbn = args.board or BOARDS[args.sketch]
    cmd = [arduino_cli(), "compile", "--fqbn", fqbn, "--library", str(LIBRARY), "--warnings", "default"]
    if args.action == "upload":
        if not args.port:
            parser.error("upload needs --port")
        cmd += ["--upload", "--port", args.port]
    result = subprocess.run([*cmd, str(SKETCHES / args.sketch)])
    if result.returncode or args.action != "upload":
        return result.returncode
    import time

    time.sleep(2.0)  # the board restarts after the upload
    return subprocess.run([sys.executable, "-m", "labdaemon", "firmware", "check", args.port]).returncode


if __name__ == "__main__":
    sys.exit(main())
