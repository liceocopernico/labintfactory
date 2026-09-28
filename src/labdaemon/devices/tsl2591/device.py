"""The photometer device plugin: TSL2591 light sensor and LED light source on one board function."""

from collections.abc import Mapping
from typing import Any

from labdaemon.core.capabilities import LightReading, LightSensor, LightSource, Sensor
from labdaemon.core.data import Channel
from labdaemon.core.device import Command, Device
from labdaemon.core.i18n import N_, _
from labdaemon.core.parameters import Parameter
from labdaemon.devices.tsl2591 import lux as tsl
from labdaemon.devices.tsl2591.simulated import LED_RANGES, simulated_board

# LED colour names are shown translated in forms
COLOR_NAMES = (N_("red"), N_("orange"), N_("green"), N_("blue"))


class Tsl2591Photometer(Device):
    """Implements LightSensor, LightSource and Sensor (see core.capabilities)."""

    id = "tsl2591_photometer"
    name = N_("Photometer (TSL2591 + LED)")
    models = frozenset({"photometer"})
    capabilities = frozenset({LightSensor, LightSource, Sensor})
    simulated = staticmethod(simulated_board)

    # ── settings ──
    def parameters(self, values: Mapping[str, Any]) -> list[Parameter]:
        color = values.get("led_color", "red")
        lo, hi = LED_RANGES.get(color, LED_RANGES["red"])
        return [
            Parameter("led_color", N_("LED colour"), str, "red", choices=tuple(LED_RANGES)),
            Parameter("led_power", N_("LED power"), int, lo, minimum=lo, maximum=hi, step=10),
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
        values = self.params.values() | {
            "led_color": led.str("color"), "led_power": led.int("power"),
            "integration_time": cfg.int("int"), "gain": cfg.int("gain")}
        self.params.replace(self.parameters(values), values)

    def apply_settings(self, values: Mapping[str, Any], changed: str) -> None:
        if changed in ("led_color", "led_power"):
            self.wire.query("LED", values["led_color"], values["led_power"])
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
        r = self.wire.run("READ", n, timeout=n * t / 1000 + 1.0)
        ch0, ch1 = r.int("bb"), r.int("ir")
        full = tsl.full_scale_counts(t)
        return LightReading(lux=tsl.lux(ch0, ch1, t, g), broadband=ch0, infrared=ch1,
                            saturated=r.bool("sat", False) or max(ch0, ch1) >= full)

    # ── LightSource ──
    def colors(self) -> list[str]:
        return list(LED_RANGES)

    def power_range(self, color: str) -> tuple[int, int]:
        return LED_RANGES[color]

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
