"""Measured quantities: channels and datasets."""

import csv
import io
import math
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from labdaemon.core.events import Signal
from labdaemon.core.i18n import _


@dataclass(frozen=True)
class Channel:
    key: str  # "lux"
    label: str  # English source text (N_)
    unit: str  # symbols ("lx", "mT") are shown as they are; words ("counts") are marked with N_()
    symbol: str = ""  # short column heading, as in a lab report ("c", "I", "A"); the label when empty

    @property
    def heading(self) -> str:
        return self.symbol or self.label

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "unit": self.unit, "symbol": self.symbol}

    @classmethod
    def from_dict(cls, d: Mapping[str, str]) -> Channel:
        return cls(d["key"], d.get("label", d["key"]), d.get("unit", ""), d.get("symbol", ""))


# CSV flavours: the international default, and what Excel expects with Italian regional settings.
CSV_PRESETS = {"international": (",", "."), "excel-it": (";", ",")}


class Dataset:
    """A table of measurements: one row per point, one column per channel. Safe to append from any thread."""

    def __init__(self, name: str, channels: Iterable[Channel], metadata: Mapping[str, Any] | None = None) -> None:
        self.name = name
        self.channels = list(channels)
        self.metadata: dict[str, Any] = dict(metadata or {})
        self._rows: list[tuple[Any, ...]] = []
        self._lock = threading.RLock()
        self.changed = Signal(f"dataset.{name}.changed")  # () after any change

    @property
    def keys(self) -> list[str]:
        return [c.key for c in self.channels]

    def __len__(self) -> int:
        with self._lock:
            return len(self._rows)

    def append(self, **values: Any) -> int:
        row = self._row(values)
        with self._lock:
            self._rows.append(row)
            index = len(self._rows) - 1
        self.changed.emit()
        return index

    def update(self, index: int, **values: Any) -> None:
        with self._lock:
            current = dict(zip(self.keys, self._rows[index], strict=True))
            current.update(values)
            self._rows[index] = self._row(current)
        self.changed.emit()

    def remove(self, index: int) -> None:
        with self._lock:
            del self._rows[index]
        self.changed.emit()

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()
        self.changed.emit()

    def row(self, index: int) -> dict[str, Any]:
        with self._lock:
            return dict(zip(self.keys, self._rows[index], strict=True))

    def rows(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(zip(self.keys, r, strict=True)) for r in self._rows]

    def column(self, key: str) -> np.ndarray:
        i = self.keys.index(key)
        with self._lock:
            return np.array([r[i] for r in self._rows], dtype=float)

    def _row(self, values: Mapping[str, Any]) -> tuple[Any, ...]:
        unknown = set(values) - set(self.keys)
        if unknown:
            raise KeyError(f"{self.name} has no channel {sorted(unknown)}")
        return tuple(values.get(k, math.nan) for k in self.keys)

    # ── files ──
    def write_csv(self, out: TextIO, preset: str = "international") -> None:
        sep, decimal = CSV_PRESETS[preset]
        writer = csv.writer(out, delimiter=sep, lineterminator="\n")
        writer.writerow([f"{_(c.label)} ({_(c.unit)})" if c.unit else _(c.label) for c in self.channels])
        for row in self.rows():
            writer.writerow([_format(row[k], decimal) for k in self.keys])

    def to_csv(self, path: Path | None = None, preset: str = "international") -> str:
        buffer = io.StringIO()
        self.write_csv(buffer, preset)
        text = buffer.getvalue()
        if path is not None:
            Path(path).write_text(text, encoding="utf-8-sig" if preset == "excel-it" else "utf-8")
        return text

    def read_csv(self, text: str, preset: str = "international") -> None:
        """Replace the rows with those of a CSV written by write_csv (columns in channel order)."""
        sep, decimal = CSV_PRESETS[preset]
        rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=sep))[1:]
        with self._lock:
            self._rows = [tuple(_parse(cell, decimal) for cell in r) for r in rows if r]
        self.changed.emit()

    def to_pandas(self):
        import pandas as pd  # optional: pip install labdaemon[jupyter]

        return pd.DataFrame(self.rows(), columns=self.keys)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "channels": [c.to_dict() for c in self.channels], "metadata": self.metadata}


def _format(value: Any, decimal: str) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        text = repr(value)
    else:
        text = str(value)
    return text.replace(".", decimal) if decimal != "." and isinstance(value, float) else text


def _parse(cell: str, decimal: str) -> Any:
    if cell == "":
        return math.nan
    candidate = cell.replace(decimal, ".") if decimal != "." else cell
    try:
        return float(candidate)
    except ValueError:
        return cell
