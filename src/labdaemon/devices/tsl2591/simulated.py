"""Simulated photometer firmware: the same commands as the real board, with a Beer–Lambert sample.

Numbers are chosen so that the design's examples come out: red LED at power 1850, 100 ms, gain 25×
and an empty cuvette read 5 691 / 1 899 counts, i.e. 412.4 lx.
"""

import random
from typing import Any

from labdaemon.devices.tsl2591 import lux as tsl
from labdaemon.transports.simulated import (
    ERR_ARGUMENT,
    ERR_RANGE,
    SimError,
    SimFunction,
    WireSimulator,
    arg_int,
)
from labdaemon.transports.wire import parse_fields

LED_RANGES = {"red": (100, 4000), "orange": (780, 850), "green": (780, 900), "blue": (780, 850)}
_K = 5691 / (1850 * 100 * 25)  # counts per (power · ms · gain) for the red LED
_EFFICIENCY = {"red": 1.0, "orange": 1.6, "green": 2.2, "blue": 2.6}
_IR_FRACTION = {"red": 1899 / 5691, "orange": 0.27, "green": 0.12, "blue": 0.08}


class PhotometerFunction(SimFunction):
    name = "photometer"
    hw = {"sensor": "tsl2591", "leds": "rgbo-5mm"}

    def __init__(self, *, noise: float = 0.002, seed: int | None = None) -> None:
        self.noise = noise
        self.rng = random.Random(seed)
        self.reset()

    def reset(self) -> None:
        self.color, self.power = "red", 1850
        self.integration_ms, self.gain = 100, 25
        self.absorbance = 0.0  # what is in the cuvette (simulation only: SIM absorbance=…)

    def handlers(self) -> dict[str, Any]:
        return {"LED": self._led, "LED?": self._led_q, "CFG": self._cfg, "CFG?": self._cfg_q,
                "READ": self._read, "SIM": self._sim}

    def _led(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] not in LED_RANGES:
            raise SimError(ERR_ARGUMENT, f"colour must be one of {','.join(LED_RANGES)}")
        lo, hi = LED_RANGES[args[0]]
        power = arg_int(args, 1, lo, 0, 4095)
        if power and not lo <= power <= hi:
            raise SimError(ERR_RANGE, f"power out of range {lo}..{hi}")
        self.color, self.power = args[0], power
        return {}

    def _led_q(self, args: list[str]) -> dict[str, Any]:
        return {"color": self.color, "power": self.power}

    def _cfg(self, args: list[str]) -> dict[str, Any]:
        t = arg_int(args, 0, self.integration_ms, 100, 600)
        g = arg_int(args, 1, self.gain, 1, 9876)
        if t not in tsl.INTEGRATION_MS or g not in tsl.GAINS:
            raise SimError(ERR_RANGE, "integration 100..600 in steps of 100; gain 1, 25, 428 or 9876")
        self.integration_ms, self.gain = t, g
        return self._cfg_q([])

    def _cfg_q(self, args: list[str]) -> dict[str, Any]:
        return {"int": self.integration_ms, "gain": self.gain}

    def _read(self, args: list[str]) -> dict[str, Any]:
        n = arg_int(args, 0, 1, 1, 15)
        full = tsl.full_scale_counts(self.integration_ms)
        base = _K * _EFFICIENCY[self.color] * self.power * self.integration_ms * self.gain
        base *= 10 ** -self.absorbance
        ch0 = ch1 = 0.0
        for _ in range(n):
            c0 = base * (1 + self.rng.gauss(0, self.noise))
            ch0 += min(c0, full)
            ch1 += min(c0 * _IR_FRACTION[self.color], full)
        ch0, ch1 = round(ch0 / n), round(ch1 / n)
        return {"bb": ch0, "ir": ch1, "sat": int(ch0 >= full or ch1 >= full)}

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
