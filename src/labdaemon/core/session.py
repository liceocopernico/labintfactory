"""Sessions: everything one lab produces, saved as one .labint file (a zip anyone can open):

    session.json          experiment, mode, parameters, devices, calibrations, results, notes …
    datasets/<name>.csv   one table per dataset
    log.txt               what happened, with times
"""

import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from labdaemon import __version__
from labdaemon.core.data import Channel, Dataset
from labdaemon.core.errors import LabError
from labdaemon.core.i18n import _

FORMAT_VERSION = 1
SUFFIX = ".labint"


def now() -> datetime:
    return datetime.now(UTC).astimezone()


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


@dataclass
class Session:
    experiment_id: str
    experiment_version: str = ""
    title: str = ""
    group: str = ""  # student group or names, asked under the student lock
    mode: str = "script"  # guided | expert | script
    created: datetime = field(default_factory=now)
    app_version: str = __version__
    parameters: dict[str, Any] = field(default_factory=dict)
    devices: list[dict[str, Any]] = field(default_factory=list)
    calibrations: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    datasets: dict[str, Dataset] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    wizard_step: int = 0

    def dataset(self, name: str, channels: list[Channel] | None = None) -> Dataset:
        if name not in self.datasets:
            if channels is None:
                raise KeyError(name)
            self.datasets[name] = Dataset(name, channels)
        return self.datasets[name]

    def note(self, text: str) -> None:
        self.log.append(f"{now():%H:%M:%S} {text}")

    def default_filename(self) -> str:
        """2026-09-28_1432_absorbance_copper-sulfate.labint: sortable, and no ':' (not allowed on Windows)."""
        parts = [f"{self.created:%Y-%m-%d_%H%M}", slug(self.experiment_id)]
        for extra in (self.title, self.group):
            if slug(extra):
                parts.append(slug(extra))
        return "_".join(parts) + SUFFIX

    # ── files ──
    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "labint", "format_version": FORMAT_VERSION, "app_version": self.app_version,
            "experiment": {"id": self.experiment_id, "version": self.experiment_version},
            "title": self.title, "group": self.group, "mode": self.mode, "created": self.created.isoformat(),
            "parameters": self.parameters, "devices": self.devices, "calibrations": self.calibrations,
            "results": self.results, "notes": self.notes, "wizard_step": self.wizard_step,
            "datasets": [d.to_dict() for d in self.datasets.values()],
        }

    def save(self, path: Path) -> Path:
        path = Path(path)
        if path.suffix != SUFFIX:
            path = path.with_suffix(SUFFIX)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("session.json", json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str))
            for d in self.datasets.values():
                z.writestr(f"datasets/{d.name}.csv", d.to_csv())
            z.writestr("log.txt", "\n".join(self.log) + "\n")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> Session:
        try:
            with zipfile.ZipFile(path) as z:
                meta = json.loads(z.read("session.json").decode("utf-8"))
                if meta.get("format") != "labint":
                    raise LabError(_("{name} is not a LabDaemon session.").format(name=Path(path).name))
                if int(meta.get("format_version", 0)) > FORMAT_VERSION:
                    raise LabError(_("{name} was saved by a newer LabDaemon. Update LabDaemon to open it.")
                                   .format(name=Path(path).name))
                session = cls(
                    experiment_id=meta["experiment"]["id"], experiment_version=meta["experiment"].get("version", ""),
                    title=meta.get("title", ""), group=meta.get("group", ""), mode=meta.get("mode", "script"),
                    created=datetime.fromisoformat(meta["created"]), app_version=meta.get("app_version", ""),
                    parameters=meta.get("parameters", {}), devices=meta.get("devices", []),
                    calibrations=meta.get("calibrations", []), results=meta.get("results", {}),
                    notes=meta.get("notes", ""), wizard_step=int(meta.get("wizard_step", 0)))
                for d in meta.get("datasets", []):
                    dataset = Dataset(d["name"], [Channel.from_dict(c) for c in d["channels"]], d.get("metadata"))
                    dataset.read_csv(z.read(f"datasets/{d['name']}.csv").decode("utf-8"))
                    session.datasets[dataset.name] = dataset
                if "log.txt" in z.namelist():
                    session.log = [line for line in z.read("log.txt").decode("utf-8").splitlines() if line]
                return session
        except (zipfile.BadZipFile, KeyError, ValueError) as e:
            raise LabError(_("{name} is damaged or not a LabDaemon session.").format(name=Path(path).name),
                           detail=str(e)) from e
