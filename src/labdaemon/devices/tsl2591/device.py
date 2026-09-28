"""The photometer device plugin: TSL2591 light sensor and LED light source on one board function."""

import time
from collections.abc import Mapping
from typing import Any

from labdaemon.core.capabilities import LightReading, LightSensor, LightSource, Sensor
from labdaemon.core.data import Channel
from labdaemon.core.device import Command, Device
from labdaemon.core.errors import LabError
from labdaemon.core.hardware import OperatingValue
from labdaemon.core.i18n import N_, _
from labdaemon.core.parameters import Parameter
from labdaemon.devices.tsl2591 import lux as tsl
from labdaemon.devices.tsl2591.simulated import COLORS, simulated_board

# LED colour names are shown translated in forms
COLOR_NAMES = (N_("red"), N_("orange"), N_("green"), N_("blue"))

# Highest drive level (DAC, 0–4095) per LED colour, from the hardware sheet.
LED_MAX = dict(tsl.sheet().spec("led", "max_power"))


class Tsl2591Photometer(Device):
    """Implements LightSensor, LightSource and Sensor (see core.capabilities)."""

    id = "tsl2591_photometer"
    name = N_("Photometer (TSL2591 + LED)")
    models = frozenset({"photometer"})
    capabilities = frozenset({LightSensor, LightSource, Sensor})
    simulated = staticmethod(simulated_board)
    hardware = "hardware/hardware.toml"
    _last: LightReading | None = None

    # ── settings ──
    def parameters(self, values: Mapping[str, Any]) -> list[Parameter]:
        color = values.get("led_color", "red")
        return [
            Parameter("led_color", N_("LED colour"), str, "red", choices=COLORS,
                      help=N_("The colour of the LED fitted in the photometer. It sets the allowed power.")),
            Parameter("led_power", N_("LED power"), int, 0, minimum=0, maximum=LED_MAX.get(color, 4000), step=10,
                      help=N_("Drive level of the LED, 0 = off.")),
            Parameter("integration_time", N_("Integration time"), int, 100, unit="ms",
                      choices=tsl.INTEGRATION_MS),
            Parameter("gain", N_("Analog gain"), int, 25, choices=tsl.GAINS, advanced=True,
                      help=N_("Nominal amplification: 1×, 25×, 428× or 9876×.")),
            Parameter("samples", N_("Readings per value"), int, 1, minimum=1, maximum=15,
                      help=N_("Each value is the mean of this many conversions.")),
        ]

    def open(self) -> None:
        led = self.wire.query("LED?")
        cfg = self.wire.query("CFG?")
        color = led.str("color")
        values = self.params.values() | {
            "led_color": color if color in COLORS else "red", "led_power": led.int("power"),
            "integration_time": cfg.int("int"), "gain": cfg.int("gain")}
        self.params.replace(self.parameters(values), values)

    def apply_settings(self, values: Mapping[str, Any], changed: str) -> None:
        if changed == "led_color":
            self.wire.query("LEDCOLOR", values["led_color"])
            self.wire.query("LED", values["led_power"])  # the power may have been fitted to the new range
        elif changed == "led_power":
            self.wire.query("LED", values["led_power"])
        elif changed in ("integration_time", "gain"):
            self.wire.query("CFG", values["integration_time"], values["gain"])

    def commands(self) -> list[Command]:
        return [Command("refresh", N_("Read settings from device"))]

    def run_command(self, key: str) -> str | None:
        if key == "refresh":
            self.open()
            return _("Settings read from the board.")
        return super().run_command(key)

    # ── LightSensor ──
    def read_light(self, samples: int | None = None) -> LightReading:
        n = samples or self.params["samples"]
        t, g = self.params["integration_time"], self.params["gain"]
        # BUSY now, EVT DONE when the conversions are done; allow twice the nominal time plus margin
        r = self.wire.run("READ", n, timeout=n * (2 * t / 1000 + 0.25) + 1.0)
        ch0, ch1 = r.int("bb"), r.int("ir")
        full = tsl.full_scale_counts(t)
        self._last = LightReading(lux=tsl.lux(ch0, ch1, t, g), broadband=ch0, infrared=ch1,
                                  saturated=r.bool("sat", False) or max(ch0, ch1) >= full)
        return self._last

    def operating_point(self) -> list[OperatingValue]:
        t, g = self.params["integration_time"], self.params["gain"]
        full = tsl.full_scale_counts(t)
        r = self._last
        if r is None:
            return []
        values = []
        for key, label, counts in (("ch0", N_("Full spectrum"), r.broadband), ("ch1", N_("Infrared"), r.infrared)):
            fraction = counts / full
            values.append(OperatingValue(key, label, counts, N_("counts"), fraction,
                                         "err" if fraction >= 1 else "warn" if fraction > 0.8 else "ok"))
        per_count = r.lux / r.broadband if r.broadband else 1 / tsl.counts_per_lux(t, g)
        values.append(OperatingValue("resolution", N_("Resolution"), per_count, N_("lx per count")))
        if r.broadband:
            saturation = r.lux * full / max(r.broadband, r.infrared)
            values.append(OperatingValue("saturation", N_("Saturates at about"), saturation, "lx",
                                         tone="err" if r.saturated else "ok"))
        return values

    # ── LightSource ──
    def colors(self) -> list[str]:
        return list(COLORS)

    def power_range(self, color: str) -> tuple[int, int]:
        return 0, LED_MAX[color]

    def set_output(self, color: str, power: int) -> None:
        self.set_parameter("led_color", color)
        self.set_parameter("led_power", power)

    # ── Sensor ──
    def channels(self) -> list[Channel]:
        return [Channel("lux", N_("Illuminance"), "lx"),
                Channel("ch0", N_("Full spectrum"), N_("counts")),
                Channel("ch1", N_("Infrared"), N_("counts")),
                Channel("full_scale", N_("Full scale"), N_("counts"))]

    def read(self) -> dict[str, float]:
        r = self.read_light()
        return {"lux": r.lux, "ch0": r.broadband, "ch1": r.infrared,
                "full_scale": tsl.full_scale_counts(self.params["integration_time"]),
                "saturated": float(r.saturated)}

    def poll(self) -> dict[str, float] | None:
        return self.read()


def _firmware_checks(channel):
    """Photometer-specific checks for `labdaemon firmware check` (firmware/PROTOCOL.md §9)."""
    from labdaemon.core.conformance import Check

    checks = []
    try:
        led = channel.query("LED?")
        checks.append(Check("photometer: LED? reports power and colour", "power" in led and "color" in led,
                            f"power={led.get('power')} color={led.get('color')}"))
        cfg = channel.query("CFG?")
        checks.append(Check("photometer: CFG? reports integration and gain", "int" in cfg and "gain" in cfg,
                            f"int={cfg.get('int')} ms gain={cfg.get('gain')}"))
        diag = channel.query("DIAG?")
        checks.append(Check("photometer: the TSL2591 answers", diag.get("sensor") == "ok",
                            f"sensor={diag.get('sensor')}"))
        op = channel.start("READ", 1)
        answered_busy = not op.done()  # OK straight away would break the 500 ms rule for long reads
        deadline = time.monotonic() + 3.0
        while not op.done() and time.monotonic() < deadline:
            channel.client.pump(0.05)
        result = op.wait(0) if op.done() else None
        checks.append(Check("photometer: READ answers BUSY, then EVT DONE with bb, ir, sat",
                            answered_busy and result is not None and all(k in result for k in ("bb", "ir", "sat")),
                            f"bb={result.get('bb')} ir={result.get('ir')} sat={result.get('sat')}" if result
                            else "no EVT DONE within 3 s"))
    except LabError as e:
        checks.append(Check("photometer: commands", False, f"{e.message} {e.detail or ''}".strip()))
    return checks


Tsl2591Photometer.firmware_checks = staticmethod(_firmware_checks)
