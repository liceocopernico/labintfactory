import time

import pytest

from labdaemon.core.errors import DeviceError, Interrupted, ProtocolTimeout, UnsupportedProtocol
from labdaemon.transports.simulated import Busy, SimFunction, SimulatedTransport, WireSimulator
from labdaemon.transports.wire import WireClient, format_line, format_value, parse_fields, tokenize


class Stepper(SimFunction):
    name = "linear-actuator"
    hw = {"driver": "tmc2209"}

    def handlers(self):
        return {"MOVE": self._move, "POS?": lambda a: {"pos": 0.0}}

    def _move(self, args):
        target = float(args[0])
        self.sim.debug("moving")
        return Busy(0.3, {"pos": f"{target:.3f}"}, stopped=lambda f: {"pos": f"{target * f:.3f}"})


class Thermo(SimFunction):
    name = "thermometer"

    def handlers(self):
        return {"READ?": lambda a: {"t": 21.37}}


def client(*functions, **options):
    sim = WireSimulator(list(functions), name="Bench-5", **options)
    t = SimulatedTransport(sim)
    t.open()
    return WireClient(t), sim


def test_line_format_round_trip():
    assert tokenize('WIFI ssid="Lab 2" psk="a\\"b" 1.5') == ["WIFI", "ssid=Lab 2", 'psk=a"b', "1.5"]
    assert format_value(2.0) == "2" and format_value(0.25) == "0.25" and format_value(True) == "1"
    assert format_line("WIFI", ssid="Lab 2") == 'WIFI ssid="Lab 2"'
    assert parse_fields(tokenize(format_line("OK", name='say "hi"'))[1:]) == {"name": 'say "hi"'}


def test_identify_and_commands():
    wire, _sim = client(Stepper(), Thermo())
    assert wire.wait_boot(1.0)
    info = wire.identify()
    assert info.name == "Bench-5" and info.functions == ("linear-actuator", "thermometer")
    assert wire.query("READ?", fn="thermometer").float("t") == pytest.approx(21.37)
    assert wire.query("HW?", fn="linear-actuator").str("driver") == "tmc2209"
    with pytest.raises(DeviceError) as err:
        wire.query("NOPE", fn="thermometer")
    assert err.value.code == 1
    with pytest.raises(DeviceError):
        wire.query("READ?")  # two functions: the prefix is required


def test_operation_done_and_debug_lines():
    wire, _sim = client(Stepper(), Thermo())
    debug = []
    wire.debug.connect(debug.append)
    op = wire.start("MOVE", 42.5, fn="linear-actuator")
    assert not op.done()
    # while the stepper moves, the other function still answers
    assert wire.query("READ?", fn="thermometer").float("t") > 0
    with pytest.raises(DeviceError) as busy:
        wire.query("MOVE", 1, fn="linear-actuator")
    assert busy.value.code == 4
    deadline = time.monotonic() + 2
    while not op.done() and time.monotonic() < deadline:
        wire.pump(0.05)
    assert op.wait(0).float("pos") == 42.5
    assert debug == ["moving"]


def test_stop_interrupts_an_operation():
    wire, _sim = client(Stepper())
    op = wire.start("MOVE", 300, fn="linear-actuator")
    time.sleep(0.1)
    assert wire.query("STOP").status == "OK"
    wire.pump(0.05)
    with pytest.raises(Interrupted):
        op.wait(1)
    stopped_at = op.event().float("pos")
    assert 0 < stopped_at < 300


def test_run_waits_for_done():
    wire, _sim = client(Stepper())
    assert wire.run("MOVE", 7, fn="linear-actuator", timeout=2).float("pos") == 7.0


def test_silent_board_times_out():
    wire, _sim = client(Thermo(), silent=True)
    t0 = time.monotonic()
    with pytest.raises(ProtocolTimeout):
        wire.query("PING", timeout=0.2)
    assert time.monotonic() - t0 < 0.5


def test_auth_required_when_token_set():
    wire, _sim = client(Thermo(), token="K7Q2M9XD")
    with pytest.raises(DeviceError) as err:
        wire.query("ID?")
    assert err.value.code == 8
    assert wire.query("AUTH", "K7Q2M9XD").status == "OK"
    assert wire.identify().functions == ("thermometer",)


def test_unsupported_protocol_version():
    wire, sim = client(Thermo())
    import labdaemon.transports.simulated as simulated

    original = simulated.PROTOCOL_VERSION
    simulated.PROTOCOL_VERSION = 99
    try:
        with pytest.raises(UnsupportedProtocol):
            wire.identify()
    finally:
        simulated.PROTOCOL_VERSION = original
