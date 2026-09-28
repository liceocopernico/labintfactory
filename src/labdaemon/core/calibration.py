"""Calibrations: reusable across sessions, with the conditions they are valid for."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from labdaemon.core.analysis import LinearFit
from labdaemon.core.session import now, slug


@dataclass
class Calibration:
    kind: str  # "absorbance.linear"
    label: str
    fit: dict[str, Any]  # LinearFit.to_dict()
    points: list[list[float]]  # [[x, y], …] including the blank
    conditions: dict[str, Any] = field(default_factory=dict)  # LED colour and power, integration, gain, path …
    device: dict[str, Any] = field(default_factory=dict)  # plugin, serial, name
    units: dict[str, str] = field(default_factory=dict)  # {"x": "mol/L", "y": ""}
    created: str = field(default_factory=lambda: now().isoformat(timespec="seconds"))
    path: Path | None = None  # where the library keeps it

    def linear_fit(self) -> LinearFit:
        return LinearFit.from_dict(self.fit, self.units.get("x", ""), self.units.get("y", ""))

    def differences(self, conditions: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
        """Conditions that differ now from when the calibration was made: key → (then, now)."""
        return {k: (v, conditions.get(k)) for k, v in self.conditions.items()
                if k in conditions and conditions[k] != v}

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "created": self.created, "device": self.device,
                "conditions": self.conditions, "units": self.units, "points": self.points, "fit": self.fit}

    @classmethod
    def from_dict(cls, d: dict[str, Any], path: Path | None = None) -> Calibration:
        return cls(kind=d["kind"], label=d.get("label", ""), fit=d["fit"], points=d.get("points", []),
                   conditions=d.get("conditions", {}), device=d.get("device", {}), units=d.get("units", {}),
                   created=d.get("created", ""), path=path)


class CalibrationLibrary:
    """Calibrations as JSON files in a folder (per user, or a shared folder set by the machine policy)."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)

    def list(self, kind: str | None = None) -> list[Calibration]:
        found = []
        for path in sorted(self.folder.glob("*.json"), reverse=True):
            try:
                cal = Calibration.from_dict(json.loads(path.read_text(encoding="utf-8")), path)
            except (OSError, ValueError, KeyError) as e:
                logger.warning("skipping unreadable calibration {}: {}", path, e)
                continue
            if kind is None or cal.kind == kind:
                found.append(cal)
        return found

    def save(self, cal: Calibration) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = cal.created[:16].replace(":", "").replace("T", "_")
        path = self.folder / f"{stamp}_{slug(cal.kind)}_{slug(cal.label) or 'calibration'}.json"
        path.write_text(json.dumps(cal.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        cal.path = path
        return path

    def delete(self, cal: Calibration) -> None:
        if cal.path is not None:
            cal.path.unlink(missing_ok=True)
