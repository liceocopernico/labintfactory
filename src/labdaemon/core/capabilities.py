"""Capabilities: what experiments ask for, and what devices provide.

Experiments only ever talk to devices through these interfaces, so any device that provides a
capability (real, simulated, from another manufacturer) can serve the experiment.
Capabilities only grow by adding methods with default implementations; anything else is a breaking
change and bumps core.API_VERSION.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from labdaemon.core.data import Channel


@dataclass(frozen=True)
class LightReading:
    lux: float
    broadband: int  # raw full-spectrum counts (visible + IR)
    infrared: int  # raw infrared counts
    saturated: bool


@dataclass(frozen=True)
class FieldReading:
    bx: float
    by: float
    bz: float
    unit: str = "mT"


@runtime_checkable
class Sensor(Protocol):
    """The generic view every sensor offers: named channels with units."""

    def channels(self) -> list[Channel]: ...

    def read(self) -> dict[str, float]: ...


@runtime_checkable
class LightSensor(Protocol):
    def read_light(self, samples: int = 1) -> LightReading: ...


@runtime_checkable
class LightSource(Protocol):
    def colors(self) -> list[str]: ...

    def power_range(self, color: str) -> tuple[int, int]: ...

    def set_output(self, color: str, power: int) -> None: ...


@runtime_checkable
class TemperatureSensor(Protocol):
    def read_temperature(self) -> float: ...  # °C


@runtime_checkable
class MagneticFieldSensor(Protocol):
    def read_field(self, window_ms: int, samples: int) -> FieldReading: ...


@runtime_checkable
class LinearActuator(Protocol):
    travel_mm: float

    def position_mm(self) -> float: ...

    def move_to(self, mm: float) -> object: ...  # an Operation; through a proxy, returns when reached

    def home(self) -> object: ...

    def stop(self) -> None: ...


ALL = (Sensor, LightSensor, LightSource, TemperatureSensor, MagneticFieldSensor, LinearActuator)
