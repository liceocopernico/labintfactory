"""Hardware sheets: what a device is built from, its datasheet figures, and notes (design §7.4).

A device plugin ships hardware/hardware.toml next to its code. The figures are data: the plugin's
own code reads them (for example the full scale used to detect saturation), and the GUI shows them.
"""

import csv
import tomllib
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from labdaemon.core.i18n import language

_MISSING = object()


@dataclass(frozen=True)
class Component:
    id: str
    role: str
    part: str
    manufacturer: str = ""
    interface: str = ""
    datasheet_url: str = ""
    datasheet_file: Path | None = None
    specs: dict[str, Any] = field(default_factory=dict)
    charts: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatingValue:
    """One live figure for the Hardware tab: "CH0: 5 691 of 36 863 counts (15 %)"."""

    key: str
    label: str  # N_()
    value: float
    unit: str = ""
    fraction: float | None = None  # 0–1 for a gauge
    tone: str = "ok"  # ok | warn | err
    text: str = ""  # a hint in words


class HardwareSheet:
    def __init__(self, root: Path, components: list[Component]) -> None:
        self.root = root
        self.components = components

    @classmethod
    def load(cls, path: Path) -> HardwareSheet:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        root = Path(path).parent
        components = []
        for c in data.get("component", []):
            file = c.get("datasheet_file")
            components.append(Component(
                id=c["id"], role=c.get("role", ""), part=c.get("part", c["id"]),
                manufacturer=c.get("manufacturer", ""), interface=c.get("interface", ""),
                datasheet_url=c.get("datasheet_url", ""),
                datasheet_file=(root / file) if file and (root / file).exists() else None,
                specs=c.get("specs", {}), charts=c.get("charts", {})))
        return cls(root, components)

    def component(self, component_id: str) -> Component:
        for c in self.components:
            if c.id == component_id:
                return c
        raise KeyError(component_id)

    def spec(self, component_id: str, key: str, default: Any = _MISSING) -> Any:
        specs = self.component(component_id).specs
        if key in specs:
            return specs[key]
        if default is _MISSING:
            raise KeyError(f"{component_id}.{key}")
        return default

    def chart(self, component_id: str, name: str) -> list[dict[str, float]]:
        info = self.component(component_id).charts[name]
        with (self.root / info["file"]).open(encoding="utf-8", newline="") as f:
            return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]

    def notes(self, lang: str | None = None) -> str:
        """The plugin's explanations in Markdown, in the interface language if available."""
        for candidate in (lang or language(), "en"):
            path = self.root / f"notes.{candidate}.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
        return ""


@cache
def load_sheet(path: Path) -> HardwareSheet:
    return HardwareSheet.load(path)
