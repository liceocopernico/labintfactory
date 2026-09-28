"""Simulated photometer firmware: the same commands as firmware/sketches/photometer, with a
Beer–Lambert sample in the cuvette.

Numbers are chosen so that the design's examples come out: red LED at power 1850, 100 ms, gain 25×
and an empty cuvette read 5 691 / 1 899 counts, i.e. 412.4 lx.
"""

import random
from typing import Any

from labdaemon.devices.tsl2591 import lux as tsl
from labdaemon.transports.simulated import (
    ERR_ARGUMENT,
    ERR_RANGE,
    Busy,
    SimError,
    SimFunction,
    WireSimulator,
    arg_int,
)
from labdaemon.transports.wire import parse_fields

COLORS = ("red", "orange", "green", "blue")
_K = 5691 / (1850 * 100 * 25)  # counts per (power · ms · gain) with the red LED
_EFFICIENCY = {"red": 1.0, "orange": 1.6, "green": 2.2, "blue": 2.6}
_IR_FRACTION = {"red": 1899 / 5691, "orange": 0.27, "green": 0.12, "blue": 0.08}


class PhotometerFunction(SimFunction):
    name = "photometer"

    def __init__(self, *, noise: float = 0.002, seed: int | None = None, time_scale: float = 0.1) -> None:
        self.noise = noise
        self.rng = random.Random(seed)
        self.time_scale = time_scale  # 1.0 = conversions take as long as on the real sensor
        self.color = "red"
        self.reset()

    @property
    def hw(self) -> dict[str, str]:  # type: ignore[override]
        return {"sensor": "tsl2591", "led": self.color}

    def reset(self) -> None:
        self.power = 0
        self.integration_ms, self.gain = 100, 25
        self.absorbance = 0.0  # what is in the cuvette (simulation only: SIM absorbance=…)

    def handlers(self) -> dict[str, Any]:
        return {"LED": self._led, "LED?": self._led_q, "LEDCOLOR": self._led_color, "CFG": self._cfg,
                "CFG?": self._cfg_q, "READ": self._read, "DIAG?": lambda a: {"sensor": "ok", "dac_bits": 12},
                "SIM": self._sim}

    def _led(self, args: list[str]) -> dict[str, Any]:
        if not args:
            raise SimError(ERR_ARGUMENT, "power required")
        self.power = arg_int(args, 0, 0, 0, 4095)
        return {"power": self.power}

    def _led_q(self, args: list[str]) -> dict[str, Any]:
        return {"power": self.power, "color": self.color}

    def _led_color(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] not in COLORS:
            raise SimError(ERR_ARGUMENT, "colour must be red, orange, green or blue")
        self.color = args[0]
        return {"color": self.color}

    def _cfg(self, args: list[str]) -> dict[str, Any]:
        t = arg_int(args, 0, self.integration_ms, 100, 600)
        g = arg_int(args, 1, self.gain, 1, 9876)
        if t % 100:
            raise SimError(ERR_RANGE, "integration in steps of 100 ms")
        if g not in tsl.GAINS:
            raise SimError(ERR_RANGE, "gain must be 1, 25, 428 or 9876")
        self.integration_ms, self.gain = t, g
        return self._cfg_q([])

    def _cfg_q(self, args: list[str]) -> dict[str, Any]:
        return {"int": self.integration_ms, "gain": self.gain}

    def _read(self, args: list[str]) -> Busy:
        n = arg_int(args, 0, 1, 1, 15)
        full = tsl.full_scale_counts(self.integration_ms)
        base = _K * _EFFICIENCY[self.color] * self.power * self.integration_ms * self.gain
        base *= 10 ** -self.absorbance
        ch0 = ch1 = 0.0
        saturated = False
        for _ in range(n):
            c0 = base * (1 + self.rng.gauss(0, self.noise))
            c1 = c0 * _IR_FRACTION[self.color]
            saturated = saturated or c0 >= full or c1 >= full
            ch0 += min(c0, full)
            ch1 += min(c1, full)
        seconds = n * self.integration_ms / 1000 * self.time_scale
        done = {"bb": round(ch0 / n), "ir": round(ch1 / n), "sat": int(saturated), "n": n}
        return Busy(seconds, done, stopped=lambda f: {"n": int(n * f)})

    def _sim(self, args: list[str]) -> dict[str, Any]:
        fields = parse_fields(args)
        if "absorbance" in fields:
            try:
                self.absorbance = max(0.0, float(fields["absorbance"]))
            except ValueError:
                raise SimError(ERR_ARGUMENT, "absorbance must be a number") from None
        return {"absorbance": self.absorbance}


def simulated_board(**options: Any) -> WireSimulator:
    return WireSimulator([PhotometerFunction(**options)], board="sim", firmware="2.0.0-sim")
