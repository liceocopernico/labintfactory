"""Expert mode: everything at once, generated from the experiment's declarations (design §4.6, mockup 5).

A plugin with no Qt code still gets this panel: its roles, parameters, operations, plot and datasets.
"""

import inspect

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.i18n import _
from labdaemon.core.wizard import TableStep
from labdaemon.gui.experiment.guided import parse_number
from labdaemon.gui.experiment.host import ExperimentHost, RoleSelector, error_text
from labdaemon.gui.widgets.components import Card, primary, set_role
from labdaemon.gui.widgets.dataset_table import DatasetTable
from labdaemon.gui.widgets.parameter_form import ParameterForm
from labdaemon.gui.widgets.plot_view import PlotView


class ExpertView(QWidget):
    def __init__(self, host: ExperimentHost) -> None:
        super().__init__()
        self.host = host
        exp = host.experiment
        table_steps = [s for s in exp.wizard() if isinstance(s, TableStep)]
        self.plot_method = next((s.plot for s in table_steps if s.plot), None)
        self.summary_method = next((s.summary for s in table_steps if s.summary), None)

        split = QSplitter()
        # left: devices, settings, operations
        left = QWidget()
        lv = QVBoxLayout(left)
        devices = Card(self.tr("Devices"))
        self.roles = RoleSelector(host)
        self.roles.assigned.connect(self.refresh)
        devices.body.addWidget(self.roles)
        lv.addWidget(devices)
        settings = Card(self.tr("Settings"))
        self.form = ParameterForm()
        self.form.edited.connect(self._edit)
        settings.body.addWidget(self.form)
        self.device_form = ParameterForm()
        self.device_form.edited.connect(self._device_edit)
        settings.body.addWidget(self.device_form)
        lv.addWidget(settings)
        operations = Card(self.tr("Measurements"))
        self.op_form = QFormLayout()
        operations.body.addLayout(self.op_form)
        self._inputs: dict[str, dict[str, QLineEdit]] = {}
        self.buttons: list[QPushButton] = []
        for op in exp.operations():
            self._add_operation(op)
        if hasattr(exp, "apply_calibration"):
            reuse = QPushButton(self.tr("Use a saved calibration…"))
            reuse.clicked.connect(self._reuse_calibration)
            operations.body.addWidget(reuse)
        lv.addWidget(operations)
        lv.addStretch()
        scroll = QScrollArea()
        scroll.setWidget(left)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(420)
        split.addWidget(scroll)

        # centre: plot and fit
        centre = Card(self.tr("Graph"))
        self.plot = PlotView()
        centre.body.addWidget(self.plot, 1)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        centre.body.addWidget(self.summary)
        self.message = QLabel()
        self.message.setWordWrap(True)
        centre.body.addWidget(self.message)
        split.addWidget(centre)

        # right: datasets
        data = Card(self.tr("Data"))
        self.tabs = QTabWidget()
        self.tables: dict[str, DatasetTable] = {}
        for name in exp.session.datasets:
            table = DatasetTable()
            self.tables[name] = table
            self.tabs.addTab(table, _(name.replace("_", " ").capitalize()))
        data.body.addWidget(self.tabs)
        split.addWidget(data)
        split.setSizes([430, 500, 380])
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(split)
        host.events.changed.connect(self.refresh)
        host.events.busy.connect(lambda busy: [b.setEnabled(not busy) for b in self.buttons])

    def _add_operation(self, op) -> None:
        inputs: dict[str, QLineEdit] = {}
        row = QHBoxLayout()
        for p in op.parameters:
            if p.name == "index":
                continue  # taken from the selected row of the data table
            field = QLineEdit()
            field.setPlaceholderText(p.name.replace("_", " "))
            field.setMaximumWidth(130)
            field.returnPressed.connect(lambda op=op: self._run(op))
            inputs[p.name] = field
            row.addWidget(field)
        button = QPushButton(_(op.label))
        if op.help:
            button.setToolTip(_(op.help))
        button.clicked.connect(lambda _c=False, op=op: self._run(op))
        if op.name.startswith("measure"):
            primary(button)
        self.buttons.append(button)
        row.addWidget(button)
        row.addStretch()
        self._inputs[op.name] = inputs
        self.op_form.addRow(row)

    def _run(self, op) -> None:
        args = []
        for p in op.parameters:
            if p.name == "index":
                table = self.tabs.currentWidget()
                if table is None or table.currentRow() < 0:
                    self.show_message(self.tr("Select a row in the data table first."), error=True)
                    return
                args.append(table.currentRow())
                continue
            text = self._inputs[op.name][p.name].text().strip()
            if not text and p.default is not inspect.Parameter.empty:
                args.append(p.default)
            elif p.annotation in (float, "float") or p.annotation is int:
                try:
                    number = parse_number(text)
                except ValueError:
                    self.show_message(self.tr("{0}: type a number.").format(p.name), error=True)
                    return
                args.append(int(number) if p.annotation is int else number)
            else:
                args.append(text)
        self.show_message(self.tr("Measuring…") if op.name.startswith("measure") else "")

        def ok(result: object) -> None:
            for field in self._inputs[op.name].values():
                field.clear()
            self.show_message(self._describe(result))

        self.host.run(op.name, *args, on_ok=ok, on_error=lambda exc: self.show_message(error_text(exc), error=True))

    def _describe(self, result: object) -> str:
        if result is None or isinstance(result, dict):
            return ""
        if isinstance(result, float):
            return QLocale().toString(result, "f", 2)
        return str(result)

    def _edit(self, key: str, value: object) -> None:
        future = self.host.runner.call(self.host.experiment.set_parameter, key, value)
        self.host.bridge.watch(future, lambda _v: self.refresh(),
                               lambda exc: (self.show_message(error_text(exc), error=True), self.refresh()))

    def _device_key(self) -> str | None:
        for role in self.host.experiment.requires:
            if key := self.host.role_key(role):
                return key
        return None

    def _device_edit(self, key: str, value: object) -> None:
        device = self._device_key()
        if device:
            future = self.host.manager.submit(device, "set_parameter", key, value)
            self.host.bridge.watch(future, lambda _v: self.refresh(),
                                   lambda exc: (self.show_message(error_text(exc), error=True), self.refresh()))

    def _reuse_calibration(self) -> None:
        library = self.host.calibrations()
        found = library.list() if library else []
        if not found:
            self.show_message(self.tr("No saved calibrations yet."), error=True)
            return
        names = [f"{c.label} · {c.created[:16].replace('T', ' ')}" for c in found]
        choice, ok = QInputDialog.getItem(self, self.tr("Use a saved calibration"), self.tr("Calibration"), names,
                                          0, False)
        if ok:
            cal = found[names.index(choice)]
            future = self.host.runner.call(self.host.experiment.apply_calibration, cal)
            self.host.bridge.watch(future, lambda _d: self.show_message(
                self.tr("Calibration “{0}” loaded. Measure the blank again before the unknowns.").format(cal.label)),
                lambda exc: self.show_message(error_text(exc), error=True))

    def devices_changed(self) -> None:
        self.roles.refresh()
        self.refresh()

    def refresh(self) -> None:
        exp = self.host.experiment
        self.form.set_parameters(exp.params.definitions(), exp.params.values())
        device = self._device_key()
        if device:
            snap = self.host.manager.snapshot(device)
            keys = exp.device_keys
            self.device_form.set_parameters([p for p in snap.parameters if keys is None or p.key in keys], snap.values)
        for name, table in self.tables.items():
            table.show_dataset(exp.session.datasets[name])
        if self.plot_method:
            self.plot.show_data(getattr(exp, self.plot_method)())
        self.summary.setText(getattr(exp, self.summary_method)() if self.summary_method else "")

    def show_message(self, text: str, *, error: bool = False) -> None:
        self.message.setText(text)
        set_role(self.message, "role", "error" if error else "muted")

