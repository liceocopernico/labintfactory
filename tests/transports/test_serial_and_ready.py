import pytest

from labdaemon.core.conformance import check_board
from labdaemon.core.registry import Registry
from labdaemon.devices.tsl2591.simulated import simulated_board
from labdaemon.transports import serial as serial_mod
from labdaemon.transports.serial import SerialTransport
from labdaemon.transports.simulated import SimulatedTransport, WireSimulator
from labdaemon.transports.wire import WireClient


class FakeSerial:
    """Delivers bytes in the chunks a USB link might, including half lines."""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.timeout = 0.1
        self.written = b""

    def read_until(self, terminator):
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, data):
        self.written += data

    def reset_input_buffer(self):
        pass


def test_serial_transport_reassembles_lines():
    t = SerialTransport("/dev/fake")
    t._serial = FakeSerial([b"OK fn=photo", b"meter power=1850\r\nEVT DONE fn=p", b"hotometer\n"])
    assert t.read_line(0.1) is None  # half a line: kept for later
    assert t.read_line(0.1) == "OK fn=photometer power=1850"
    assert t.read_line(0.1) == "EVT DONE fn=photometer"
    t.write_line("PING")
    assert t._serial.written == b"PING\n"


def test_permission_error_explains_what_to_do(monkeypatch):
    class Refusing:
        def __init__(self):
            self.port = None

        def open(self):
            raise serial_mod.serial.SerialException(13, "could not open port: [Errno 13] Permission denied")

        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

    monkeypatch.setattr(serial_mod.serial, "Serial", Refusing)
    with pytest.raises(serial_mod.PermissionDenied) as err:
        SerialTransport("/dev/ttyACM9").open()
    assert "/dev/ttyACM9" in err.value.message


@pytest.mark.parametrize("boot_event", [True, False])
def test_wait_ready_with_and_without_boot_event(boot_event):
    sim = simulated_board()
    sim.boot_event = boot_event
    t = SimulatedTransport(sim)
    t.open()
    assert WireClient(t).wait_ready(1.0)


def test_wait_ready_gives_up_on_a_silent_port():
    t = SimulatedTransport(WireSimulator([], silent=True, name="x"))
    t.open()
    assert not WireClient(t).wait_ready(0.6)


def test_simulated_photometer_passes_the_conformance_suite():
    t = SimulatedTransport(simulated_board())
    t.open()
    wire = WireClient(t)
    assert wire.wait_ready(1.0)
    info, checks = check_board(wire, Registry().load())
    failed = [c for c in checks if not c.ok]
    assert info is not None and not failed, failed
    assert len(checks) == 11


def test_scan_with_no_ports(manager, monkeypatch):
    import labdaemon.core.manager as manager_mod

    monkeypatch.setattr(manager_mod, "list_ports", lambda: [])
    assert manager.scan_serial() == []
