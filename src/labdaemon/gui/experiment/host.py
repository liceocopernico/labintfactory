"""One open experiment: its runner, its devices, and its guided and expert views (design §6–7)."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QStandardPaths, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.calibration import CalibrationLibrary
from labdaemon.core.errors import LabError
from labdaemon.core.experiment import Experiment, ExperimentRunner
from labdaemon.core.i18n import _
from labdaemon.core.manager import DeviceManager
from labdaemon.core.session import Session
from labdaemon.core.settings import Settings
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.widgets.components import PageHeader, primary


def error_text(exc: BaseException) -> str:
    return exc.message if isinstance(exc, LabError) else (str(exc) or type(exc).__name__)


class ExperimentBridge(QObject):
    """Experiment and dataset changes happen on the runner thread; this repaints once, on the GUI thread."""

    changed = Signal()
    busy = Signal(bool)
    _poke = Signal()

    def __init__(self, experiment: Experiment, runner: ExperimentRunner, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(30)  # coalesce bursts (a new blank updates every row)
        self._timer.timeout.connect(self.changed.emit)
        self._poke.connect(self._timer.start)
        experiment.changed.connect(self._poke.emit)
        for dataset in experiment.session.datasets.values():
            dataset.changed.connect(self._poke.emit)
        runner.busy.connect(self.busy.emit)


class RoleSelector(QWidget):
    """A device for each role the experiment requires, chosen among connected devices that fit."""

    assigned = Signal()

    def __init__(self, host: ExperimentHost, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.combos: dict[str, QComboBox] = {}
        for role, req in host.experiment.requires.items():
            combo = QComboBox()
            combo.activated.connect(lambda _i, role=role: self._chosen(role))
            self.combos[role] = combo
            self.form.addRow(_(req.label), combo)
        add = QPushButton(self.tr("Add device…"))
        add.clicked.connect(host.open_add_device)
        self.form.addRow("", add)
        self.refresh()

    def refresh(self) -> None:
        for role, combo in self.combos.items():
            req = self.host.experiment.requires[role]
            keys = self.host.manager.devices_providing(req.capability)
            current = self.host.role_keys.get(role)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(self.tr("— choose —") if keys else self.tr("No suitable device connected"), None)
            for key in keys:
                combo.addItem(self.host.device_name(key), key)
            combo.setCurrentIndex(max(0, combo.findData(current)))
            combo.blockSignals(False)

    def _chosen(self, role: str) -> None:
        self.host.assign(role, self.combos[role].currentData())
        self.assigned.emit()


class ExperimentHost(QWidget):
    closed = Signal(object)  # self

    def __init__(self, experiment: Experiment, manager: DeviceManager, bridge: QtBridge, settings: Settings,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.experiment = experiment
        self.manager = manager
        self.bridge = bridge
        self.settings = settings
        self.runner = ExperimentRunner(experiment)
        self.events = ExperimentBridge(experiment, self.runner, self)
        self.role_keys: dict[str, str] = {}
        self.live: dict[str, dict[str, float]] = {}  # device key → latest sample
        self.saved_path: Path | None = None
        self.dirty = False
        self.events.changed.connect(self._mark_dirty)

        v = QVBoxLayout(self)
        head = QHBoxLayout()
        self.header = PageHeader(_(experiment.name))
        head.addWidget(self.header, 1)
        self.mode_buttons = QButtonGroup(self)
        for mode, label in (("guided", self.tr("Guided")), ("expert", self.tr("Expert"))):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("mode", mode)
            self.mode_buttons.addButton(button)
            head.addWidget(button)
        self.mode_buttons.buttonClicked.connect(lambda b: self.set_mode(b.property("mode")))
        save = primary(QPushButton(self.tr("Save session…")))
        save.clicked.connect(lambda: self.save_session())
        close = QPushButton(self.tr("Close"))
        close.clicked.connect(lambda: self.close_experiment())
        head.addWidget(save)
        head.addWidget(close)
        v.addLayout(head)

        from labdaemon.gui.experiment.expert import ExpertView
        from labdaemon.gui.experiment.guided import GuidedView

        self.guided = GuidedView(self)
        self.expert = ExpertView(self)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.guided)
        self.stack.addWidget(self.expert)
        v.addWidget(self.stack, 1)

        bridge.boards_changed.connect(self._devices_changed)
        bridge.sample.connect(self._on_sample)
        self._devices_changed()
        self.set_mode(self._initial_mode())
        self._update_header()
        self.events.changed.connect(self._update_header)

    # ── devices ──
    def device_name(self, key: str) -> str:
        try:
            snap = self.manager.snapshot(key)
        except LabError:
            return key
        return f"{snap.board.name} · {_(snap.plugin_name)}"

    def assign(self, role: str, key: str | None) -> None:
        if key:
            self.role_keys[role] = key
            self.experiment.assign(role, self.manager.proxy(key))
        else:
            self.role_keys.pop(role, None)
            self.experiment.assign(role, None)

    def _devices_changed(self) -> None:
        connected = set(self.manager.device_keys())
        for role, key in list(self.role_keys.items()):
            if key not in connected:
                self.assign(role, None)
        for role, req in self.experiment.requires.items():
            candidates = self.manager.devices_providing(req.capability)
            if role not in self.role_keys and len(candidates) == 1:
                self.assign(role, candidates[0])  # only one fits: no need to ask
        self.guided.devices_changed()
        self.expert.devices_changed()

    def open_add_device(self) -> None:
        from labdaemon.gui.views.add_device import AddDeviceDialog

        AddDeviceDialog(self.manager, self.bridge, self).exec()

    def role_key(self, role: str) -> str | None:
        return self.role_keys.get(role)

    def _on_sample(self, key: str, values: dict, _t: float) -> None:
        if key in self.role_keys.values():
            self.live[key] = values
            self.guided.live_changed()

    # ── operations ──
    def run(self, name: str, *args: Any, on_ok=None, on_error=None) -> None:
        future = self.runner.action(name, *args)
        self.bridge.watch(future, on_ok, on_error)

    # ── modes ──
    def _mode_key(self) -> str:
        return f"experiments.{self.experiment.id}.mode"

    def _initial_mode(self) -> str:
        return self.settings.get(self._mode_key(), "guided")

    def set_mode(self, mode: str) -> None:
        self.stack.setCurrentWidget(self.guided if mode == "guided" else self.expert)
        for button in self.mode_buttons.buttons():
            button.setChecked(button.property("mode") == mode)
        self.experiment.session.mode = mode
        (self.guided if mode == "guided" else self.expert).refresh()

    def remember_mode(self, mode: str) -> None:
        try:
            self.settings.set(self._mode_key(), mode)
            self.settings.save()
        except (LabError, OSError):
            pass

    def calibrations(self) -> CalibrationLibrary | None:
        return self.experiment.calibrations

    # ── session ──
    def _mark_dirty(self) -> None:
        self.dirty = True

    def _update_header(self) -> None:
        s = self.experiment.session
        parts = [s.title or self.tr("untitled"), f"{s.created:%d/%m/%Y %H:%M}"]
        if self.saved_path:
            parts.append(self.saved_path.name + ("" if not self.dirty else " *"))
        self.header.set_text(_(self.experiment.name), " · ".join(parts))

    def sessions_folder(self) -> Path:
        return self.sessions_folder_for(self.settings)

    @staticmethod
    def sessions_folder_for(settings: Settings) -> Path:
        configured = settings.get("paths.sessions") or ""
        if configured:
            return Path(configured)
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return Path(docs or Path.home()) / "LabDaemon"

    def save_session(self, path: Path | None = None) -> Path | None:
        session = self.experiment.session
        if path is None:
            suggested = self.saved_path or self.sessions_folder() / session.default_filename()
            chosen, _filter = QFileDialog.getSaveFileName(self, self.tr("Save session"), str(suggested),
                                                          self.tr("LabDaemon sessions (*.labint)"))
            if not chosen:
                return None
            path = Path(chosen)
        try:
            self.saved_path = session.save(path)
        except OSError as e:
            QMessageBox.warning(self, self.tr("Save session"), self.tr("Could not save: {0}").format(e))
            return None
        self.dirty = False
        self._update_header()
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(self.tr("Saved {0}").format(self.saved_path), 6000)
        return self.saved_path

    def close_experiment(self, *, force: bool = False) -> bool:
        if self.dirty and not force:
            answer = QMessageBox.question(
                self, _(self.experiment.name), self.tr("Save the session before closing?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save and self.save_session() is None:
                return False
        self.runner.shutdown()
        self.closed.emit(self)
        return True

    @classmethod
    def open(cls, experiment_cls: type[Experiment], manager: DeviceManager, bridge: QtBridge, settings: Settings,
             session: Session | None = None) -> ExperimentHost:
        library = CalibrationLibrary(settings.paths.data_dir / "calibrations")
        experiment = experiment_cls({}, session, calibrations=library)
        return cls(experiment, manager, bridge, settings)
