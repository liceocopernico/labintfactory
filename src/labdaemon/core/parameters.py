"""Typed settings with limits. Devices and experiments describe their settings as Parameters;
forms, wizards and scripts all go through the same validation."""

import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from labdaemon.core.errors import ParameterError
from labdaemon.core.events import Signal
from labdaemon.core.i18n import _


@dataclass(frozen=True)
class Parameter:
    key: str
    label: str  # English source text, marked with N_(); shown through _()
    type: type
    default: Any
    unit: str | None = None
    choices: Sequence[Any] | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    advanced: bool = False  # hidden in guided mode and under the student lock
    help: str = ""

    def validate(self, value: Any) -> Any:
        """Return `value` converted to this parameter's type, or raise ParameterError. Never clamps."""
        label = _(self.label)
        try:
            if self.type is bool:
                v = value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "on")
            elif self.type is int:
                if isinstance(value, float) and not value.is_integer():
                    raise ValueError
                v = int(value)
            elif self.type is float:
                v = float(str(value).replace(",", ".")) if isinstance(value, str) else float(value)
            else:
                v = self.type(value)
        except (TypeError, ValueError):
            message = _("{label}: {value!r} is not a valid value.").format(label=label, value=value)
            raise ParameterError(message) from None
        if self.choices is not None and v not in self.choices:
            options = ", ".join(str(c) for c in self.choices)
            raise ParameterError(_("{label}: choose one of {options}.").format(label=label, options=options))
        if self.minimum is not None and v < self.minimum or self.maximum is not None and v > self.maximum:
            raise ParameterError(
                _("{label}: {value} is outside {minimum}–{maximum}{unit}.").format(
                    label=label, value=v, minimum=self.minimum, maximum=self.maximum,
                    unit=f" {self.unit}" if self.unit else ""))
        return v

    def fit(self, value: Any) -> Any:
        """Bring a *dependent* value into range after another parameter changed its limits.

        Used for consequences (the LED power when the colour changes), never for user input.
        """
        try:
            return self.validate(value)
        except ParameterError:
            pass
        if self.choices is not None:
            return self.default
        try:
            v = self.type(value)
        except (TypeError, ValueError):
            return self.default
        if self.minimum is not None and v < self.minimum:
            v = self.type(self.minimum)
        if self.maximum is not None and v > self.maximum:
            v = self.type(self.maximum)
        return v


class ParameterSet:
    """Current definitions and values. The single source of truth: widgets bind to it and keep no copy."""

    def __init__(self, parameters: Iterable[Parameter] = ()) -> None:
        self._lock = threading.Lock()
        self._defs: dict[str, Parameter] = {p.key: p for p in parameters}
        self._values: dict[str, Any] = {k: p.default for k, p in self._defs.items()}
        self.changed = Signal("parameters.changed")  # (values: dict, definitions_changed: bool)

    def definitions(self) -> list[Parameter]:
        with self._lock:
            return list(self._defs.values())

    def definition(self, key: str) -> Parameter:
        with self._lock:
            try:
                return self._defs[key]
            except KeyError:
                raise ParameterError(_("Unknown setting: {key}").format(key=key)) from None

    def values(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return self._values[key]

    def replace(self, definitions: Iterable[Parameter], values: Mapping[str, Any]) -> None:
        """Install new definitions and values together (values are assumed valid)."""
        defs = {p.key: p for p in definitions}
        with self._lock:
            defs_changed = defs != self._defs
            new_values = {k: values.get(k, p.default) for k, p in defs.items()}
            values_changed = new_values != self._values
            self._defs, self._values = defs, new_values
        if defs_changed or values_changed:
            self.changed.emit(dict(new_values), defs_changed)
