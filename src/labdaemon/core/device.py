"""Devices: the app's object for one function of a board. A device plugin is one Device subclass.

Every method here runs on the board's worker thread (core.worker), so plugin code is plain,
blocking Python and never needs locks of its own.
"""

from abc import ABC
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from labdaemon.core.board import BoardInfo
from labdaemon.core.data import Channel
from labdaemon.core.errors import ParameterError
from labdaemon.core.i18n import N_, _
from labdaemon.core.parameters import Parameter, ParameterSet

if TYPE_CHECKING:
    from labdaemon.transports.simulated import WireSimulator
    from labdaemon.transports.wire import FunctionChannel


class DeviceState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    LOST = "lost"


STATE_LABELS = {
    DeviceState.DISCONNECTED: N_("Disconnected"),
    DeviceState.CONNECTING: N_("Connecting"),
    DeviceState.READY: N_("Ready"),
    DeviceState.BUSY: N_("Busy"),
    DeviceState.ERROR: N_("Error"),
    DeviceState.LOST: N_("Connection lost"),
}


@dataclass(frozen=True)
class Command:
    """A manual action shown as a button. Identified by `key`; the label is only for display."""

    key: str
    label: str  # N_()
    help: str = ""


class Device(ABC):
    # ── plugin metadata (class level) ──
    id: ClassVar[str]  # "tsl2591_photometer"; equals the entry-point name
    name: ClassVar[str]  # N_("Photometer (TSL2591 + LED)")
    models: ClassVar[frozenset[str]]  # function names in the board's ID? reply this plugin serves
    capabilities: ClassVar[frozenset[type]]
    links: ClassVar[frozenset[str]] = frozenset({"serial", "tcp", "ble", "simulated"})
    simulated: ClassVar[Callable[[], WireSimulator] | None] = None  # builds a simulated board
    gui: ClassVar[str | None] = None  # "pkg.module:Panel", imported only by the GUI
    api: ClassVar[int] = 1

    def __init__(self, wire: FunctionChannel, board: BoardInfo) -> None:
        self.wire = wire
        self.board = board
        self.function = wire.fn
        self.params = ParameterSet()
        self.params.replace(self.parameters({}), {})

    # ── lifecycle ──
    def open(self) -> None:
        """Called once after connecting: read the board's current settings into self.params."""

    def close(self) -> None:
        """Called before disconnecting."""

    # ── settings ──
    def parameters(self, values: Mapping[str, Any]) -> list[Parameter]:
        """Parameter definitions for the given current values (limits may depend on other values)."""
        return []

    def apply_settings(self, values: Mapping[str, Any], changed: str) -> None:
        """Send `values` to the hardware; `changed` is the key the user edited."""

    def set_parameter(self, key: str, value: Any) -> dict[str, Any]:
        value = self.params.definition(key).validate(value)
        values = self.params.values() | {key: value}
        definitions = {p.key: p for p in self.parameters(values)}
        # Other values may have to follow new limits (the LED power when the colour changes).
        for k, p in definitions.items():
            if k != key:
                values[k] = p.fit(values.get(k, p.default))
        self.apply_settings(values, changed=key)
        self.params.replace(definitions.values(), values)
        return values

    def set_parameters(self, values: Mapping[str, Any]) -> None:
        for key, value in values.items():
            self.set_parameter(key, value)

    # ── actions and readings ──
    def commands(self) -> list[Command]:
        return []

    def run_command(self, key: str) -> str | None:
        """Run a Command; may return a short message for the user."""
        raise ParameterError(_("Unknown command: {key}").format(key=key))

    def channels(self) -> list[Channel]:
        return []

    def poll(self) -> dict[str, float] | None:
        """Live values for monitoring (channel key → value), or None if the device has none."""
        return None

    # ── helpers ──
    @property
    def key(self) -> str:
        return f"{self.board.serial}/{self.function}"

    @property
    def display_name(self) -> str:
        return f"{self.board.name} · {_(self.name)}"

    @classmethod
    def provides(cls, capability: type) -> bool:
        return capability in cls.capabilities
