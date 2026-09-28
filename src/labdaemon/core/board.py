"""Boards: one physical unit and its connection, hosting one or more instrument functions."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from labdaemon.core.errors import BadReply
from labdaemon.core.i18n import N_, _

LINK_LABELS = {"simulated": N_("simulated"), "serial": N_("USB"), "tcp": N_("Wi-Fi"), "ble": N_("Bluetooth")}


def link_label(link: str) -> str:
    return _(LINK_LABELS.get(link, link))


@dataclass(frozen=True)
class BoardInfo:
    """What a board says about itself in its ID? reply."""

    proto: int
    board: str  # "uno", "esp32", "teensy41", "sim" …
    firmware: str
    serial: str
    name: str
    functions: tuple[str, ...]
    links: tuple[str, ...] = ()

    @classmethod
    def from_fields(cls, values: Mapping[str, str]) -> BoardInfo:
        try:
            proto = int(values["proto"])
            serial = values["serial"]
        except (KeyError, ValueError):
            raise BadReply(_("The board's ID? reply is incomplete."), detail=repr(dict(values))) from None
        functions = tuple(f for f in values.get("functions", "").split(",") if f)
        if not functions:
            raise BadReply(_("The board reports no functions."), detail=repr(dict(values)))
        return cls(
            proto=proto,
            board=values.get("board", "?"),
            firmware=values.get("fw", "?"),
            serial=serial,
            name=values.get("name") or serial,
            functions=functions,
            links=tuple(x for x in values.get("links", "").split(",") if x),
        )


@dataclass(frozen=True)
class BoardAddress:
    """How to reach a board: the link and where on it."""

    link: str  # "simulated" | "serial" | "tcp" | "ble"
    target: str  # plugin id for simulated boards, COM port, host, BLE name …
    options: Mapping[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.link}:{self.target}"
