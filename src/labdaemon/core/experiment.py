"""Experiments: Qt-free controllers with @action (short) and @run (long) operations (design §4.6).

The wizard and the expert panel are two views that call the same operations. Operations run on the
experiment's own thread (ExperimentRunner), one at a time; devices are reached through proxies, so
the same code runs in the GUI, in Jupyter and in tests.
"""

import inspect
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, ClassVar

from labdaemon.core.calibration import CalibrationLibrary
from labdaemon.core.errors import NotReady
from labdaemon.core.events import Signal
from labdaemon.core.i18n import _
from labdaemon.core.parameters import Parameter, ParameterSet
from labdaemon.core.session import Session
from labdaemon.core.wizard import ActionStep, DevicesStep, ParametersStep, ResultStep, Step, TableStep


@dataclass(frozen=True)
class Requirement:
    capability: type
    label: str  # N_()
    optional: bool = False


@dataclass(frozen=True)
class Series:
    label: str  # N_()
    points: list[tuple[float, float]]
    kind: str = "points"  # points | line
    color: str = "a"  # a theme series: a, fit, x, y, z


@dataclass(frozen=True)
class PlotData:
    """What an experiment wants drawn; the GUI draws it with the theme's colours."""

    x_label: str
    y_label: str
    series: list[Series]


@dataclass(frozen=True)
class Operation:
    name: str
    label: str  # N_()
    help: str
    kind: str  # "action" | "run"
    parameters: tuple[inspect.Parameter, ...]  # besides self (and the RunContext of runs)


def action(label: str, *, help: str = "") -> Callable:
    """A short operation that returns a result (measure the blank, measure this standard …)."""

    def mark(fn: Callable) -> Callable:
        fn.__labdaemon_op__ = ("action", label, help)
        return fn

    return mark


def run(label: str, *, help: str = "") -> Callable:
    """A long acquisition that records until it finishes or is stopped. Its first argument is a RunContext."""

    def mark(fn: Callable) -> Callable:
        fn.__labdaemon_op__ = ("run", label, help)
        return fn

    return mark


class RunContext:
    def __init__(self) -> None:
        self._cancel = threading.Event()
        self.started = time.monotonic()
        self._next: float | None = None
        self.progressed = Signal("run.progress")  # (fraction or None, text)

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def sleep(self, seconds: float) -> bool:
        """Wait, but wake at once when the run is stopped. Returns False if it was stopped."""
        return not self._cancel.wait(max(0.0, seconds))

    def sleep_until_next(self, interval: float) -> bool:
        """Keep a steady rhythm (no drift from how long each measurement took)."""
        self._next = (self._next or self.started) + interval
        return self.sleep(self._next - time.monotonic())

    def progress(self, fraction: float | None, text: str = "") -> None:
        self.progressed.emit(fraction, text)


class Experiment:
    # ── plugin metadata ──
    id: ClassVar[str]
    name: ClassVar[str]  # N_()
    category: ClassVar[str] = "general"  # chemistry | physics | general
    description: ClassVar[str] = ""  # N_()
    requires: ClassVar[dict[str, Requirement]] = {}
    parameters: ClassVar[list[Parameter]] = []
    version: ClassVar[str] = "1.0"
    gui: ClassVar[str | None] = None
    api: ClassVar[int] = 1
    # Device settings shown with the experiment's own (None: all of them)
    device_keys: ClassVar[tuple[str, ...] | None] = None

    def __init__(self, devices: Mapping[str, Any] | None = None, session: Session | None = None, *,
                 calibrations: CalibrationLibrary | None = None) -> None:
        self.devices: dict[str, Any] = dict(devices or {})
        self.session = session or Session(experiment_id=self.id, experiment_version=self.version)
        self.calibrations = calibrations
        self.params = ParameterSet(self.parameters)
        stored = {k: v for k, v in self.session.parameters.items() if k in {p.key for p in self.parameters}}
        if stored:
            self.params.replace(self.parameters, self.params.values() | stored)
        self.session.parameters = self.params.values()
        self.done_actions: set[str] = set(self.session.results.get("_done_actions", []))
        self.changed = Signal("experiment.changed")  # () after anything the views show has changed
        self.setup()

    def setup(self) -> None:
        """Create datasets and restore state from self.session."""

    # ── devices ──
    def assign(self, role: str, device: Any) -> None:
        self.devices[role] = device
        self.changed.emit()

    def missing_roles(self) -> list[str]:
        return [role for role, req in self.requires.items() if not req.optional and self.devices.get(role) is None]

    def device(self, role: str) -> Any:
        dev = self.devices.get(role)
        if dev is None:
            raise NotReady(_("Choose a device for: {role}.").format(role=_(self.requires[role].label)))
        return dev

    # ── settings ──
    def set_parameter(self, key: str, value: Any) -> None:
        value = self.params.definition(key).validate(value)
        self.params.replace(self.parameters, self.params.values() | {key: value})
        self.session.parameters = self.params.values()
        self.changed.emit()

    # ── operations ──
    @classmethod
    def operations(cls) -> list[Operation]:
        found = []
        for name in dir(cls):
            fn = getattr(cls, name, None)
            mark = getattr(fn, "__labdaemon_op__", None)
            if mark:
                kind, label, help_ = mark
                params = list(inspect.signature(fn).parameters.values())[1:]
                if kind == "run":
                    params = params[1:]
                found.append(Operation(name, label, help_, kind, tuple(params)))
        return sorted(found, key=lambda op: getattr(cls, op.name).__code__.co_firstlineno)  # as written

    def run_operation(self, name: str, *args: Any, **kwargs: Any) -> Any:
        result = getattr(self, name)(*args, **kwargs)
        self.done_actions.add(name)
        self.session.results["_done_actions"] = sorted(self.done_actions)
        self.changed.emit()
        return result

    # ── guided mode ──
    def wizard(self) -> list[Step]:
        return []

    def step_complete(self, step: Step, live: Mapping[str, float] | None = None) -> bool:
        if isinstance(step, DevicesStep):
            return not self.missing_roles()
        if isinstance(step, ParametersStep):
            return step.check is None or getattr(self, step.check)(live or {}) is None
        if isinstance(step, ActionStep):
            return step.action in self.done_actions
        if isinstance(step, TableStep):
            count = getattr(self, step.count)() if step.count else len(self.session.datasets[step.dataset])
            return count >= step.min_rows
        return True

    def summary(self) -> list[tuple[str, str]]:
        """Results as (label, text) pairs for the result step and the session."""
        return []


class RunHandle:
    def __init__(self, context: RunContext, future: Future) -> None:
        self.context = context
        self.future = future

    def stop(self) -> None:
        self.context.cancel()

    def wait(self, timeout: float | None = None) -> Any:
        return self.future.result(timeout)

    @property
    def done(self) -> bool:
        return self.future.done()


class ExperimentRunner:
    """The experiment's own thread: operations run here one at a time, never on the GUI thread."""

    def __init__(self, experiment: Experiment) -> None:
        self.experiment = experiment
        self._pool = ThreadPoolExecutor(1, thread_name_prefix=f"experiment-{experiment.id}")
        self._pending = 0
        self._lock = threading.Lock()
        self._run: RunHandle | None = None
        self.busy = Signal("runner.busy")  # (bool)

    def action(self, name: str, *args: Any, **kwargs: Any) -> Future:
        return self._submit(self.experiment.run_operation, name, *args, **kwargs)

    def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """Run any experiment method on the experiment's thread (settings, calibrations …)."""
        return self._submit(fn, *args, **kwargs)

    def start(self, name: str, **kwargs: Any) -> RunHandle:
        context = RunContext()
        self._run = RunHandle(context, self._submit(self.experiment.run_operation, name, context, **kwargs))
        return self._run

    def stop(self) -> None:
        if self._run is not None:
            self._run.stop()

    def shutdown(self) -> None:
        self.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        with self._lock:
            self._pending += 1
            if self._pending == 1:
                self.busy.emit(True)
        future = self._pool.submit(fn, *args, **kwargs)
        future.add_done_callback(self._finished)
        return future

    def _finished(self, _future: Future) -> None:
        with self._lock:
            self._pending -= 1
            idle = self._pending == 0
        if idle:
            self.busy.emit(False)


__all__ = ["ActionStep", "DevicesStep", "Experiment", "ExperimentRunner", "Operation", "ParametersStep", "PlotData",
           "Series",
           "Requirement", "ResultStep", "RunContext", "RunHandle", "Step", "TableStep", "action", "run"]
