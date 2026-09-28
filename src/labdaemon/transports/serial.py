"""USB serial link (pyserial). Works for every board with USB CDC or a USB-serial chip."""

import errno
import sys
from dataclasses import dataclass

import serial
import serial.tools.list_ports

from labdaemon.core.errors import PermissionDenied, PortBusy, PortNotFound, TransportError
from labdaemon.core.i18n import _
from labdaemon.core.transport import Transport

BAUDRATE = 115200


@dataclass(frozen=True)
class PortInfo:
    device: str  # "/dev/ttyACM0", "COM3"
    description: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    manufacturer: str | None = None

    @property
    def usb_id(self) -> str:
        return f"{self.vid:04X}:{self.pid:04X}" if self.vid is not None and self.pid is not None else ""


def list_ports() -> list[PortInfo]:
    """USB serial ports, the only kind a LabDaemon board uses. (Linux also lists dozens of /dev/ttyS*.)"""
    ports = []
    for p in serial.tools.list_ports.comports():
        if p.vid is None and sys.platform != "win32":
            continue
        ports.append(PortInfo(p.device, p.description or p.device, p.vid, p.pid, p.serial_number,
                              p.manufacturer))
    return sorted(ports, key=lambda p: p.device)


class SerialTransport(Transport):
    kind = "serial"

    def __init__(self, port: str, *, baudrate: int = BAUDRATE) -> None:
        self.port = port
        self.baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._pending = bytearray()

    @property
    def description(self) -> str:
        return self.port

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def open(self) -> None:
        s = serial.Serial()
        s.port = self.port
        s.baudrate = self.baudrate
        s.timeout = 0.05
        s.write_timeout = 1.0
        s.dsrdtr = False
        s.rtscts = False
        if sys.platform != "win32":
            s.exclusive = True  # a second program (or LabDaemon window) cannot open it too
        try:
            s.open()
        except serial.SerialException as e:
            raise self._translate(e) from e
        self._serial = s
        self._pending.clear()

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def write_line(self, line: str) -> None:
        s = self._require()
        try:
            s.write(line.encode("ascii", "replace") + b"\n")
        except (serial.SerialException, OSError) as e:
            raise TransportError(_("Lost the connection on {port}.").format(port=self.port), detail=str(e)) from e

    def read_line(self, timeout: float) -> str | None:
        s = self._require()
        try:
            if b"\n" not in self._pending:
                s.timeout = max(0.0, timeout)
                chunk = s.read_until(b"\n")
                self._pending += chunk
                if b"\n" not in self._pending:
                    # read_until stopped at the timeout; keep whatever part arrived for next time
                    return None
        except (serial.SerialException, OSError) as e:
            raise TransportError(_("Lost the connection on {port}.").format(port=self.port), detail=str(e)) from e
        line, _sep, rest = bytes(self._pending).partition(b"\n")
        self._pending = bytearray(rest)
        return line.decode("ascii", "replace").rstrip("\r")

    def reset_input(self) -> None:
        self._pending.clear()
        if self._serial is not None:
            self._serial.reset_input_buffer()

    def _require(self) -> serial.Serial:
        if self._serial is None:
            raise TransportError(_("The connection to the board is closed."))
        return self._serial

    def _translate(self, e: serial.SerialException) -> TransportError:
        text = str(e)
        err = getattr(e, "errno", None)
        if err == errno.ENOENT or "No such file" in text or "FileNotFoundError" in text:
            return PortNotFound(_("{port} is not there any more. Is the board plugged in?").format(port=self.port),
                                detail=text)
        if err in (errno.EACCES, errno.EPERM) or "Permission denied" in text or "PermissionError" in text:
            if sys.platform.startswith("linux"):
                message = _("Permission denied on {port}. Add your user to the 'dialout' group "
                            "(or 'uucp' on Arch), then log out and back in.")
            else:
                message = _("Permission denied on {port}. Close other programs that use it.")
            return PermissionDenied(message.format(port=self.port), detail=text)
        if err == errno.EBUSY or "busy" in text.lower() or "exclusive" in text.lower():
            return PortBusy(_("{port} is in use by another program.").format(port=self.port), detail=text)
        return TransportError(_("Cannot open {port}.").format(port=self.port), detail=text)
