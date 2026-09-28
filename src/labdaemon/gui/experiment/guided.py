"""Guided mode: the experiment's wizard steps, one page each, with Back and Next (design §6, mockup 4)."""

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.i18n import _
from labdaemon.core.wizard import (
    ActionStep,
    DevicesStep,
    InstructionStep,
    ParametersStep,
    ResultStep,
    Step,
    TableStep,
)
from labdaemon.gui.experiment.host import ExperimentHost, RoleSelector, error_text
from labdaemon.gui.widgets.components import Card, PageHeader, muted, primary, scaled_font, set_role
from labdaemon.gui.widgets.dataset_table import DatasetTable, format_value
from labdaemon.gui.widgets.parameter_form import ParameterForm
from labdaemon.gui.widgets.plot_view import PlotView


def parse_number(text: str) -> float:
    """Accept 0.08 and 0,08 whatever the interface language."""
    value, ok = QLocale().toDouble(text)
    if ok:
        return value
    return float(text.strip().replace(",", "."))


class StepPage(QWidget):
    def __init__(self, view: GuidedView, step: Step) -> None:
        super().__init__()
        self.view = view
        self.host: ExperimentHost = view.host
        self.step = step
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)

    def refresh(self) -> None:
        pass

    def message(self, text: str, *, error: bool = False) -> None:
        self.view.show_message(text, error=error)


class DevicesPage(StepPage):
    def __init__(self, view: GuidedView, step: DevicesStep) -> None:
        super().__init__(view, step)
        card = Card(self.tr("Devices for this experiment"))
        self.roles = RoleSelector(self.host)
        self.roles.assigned.connect(view.refresh)
        card.body.addWidget(self.roles)
        self.layout_.addWidget(card)
        self.layout_.addStretch()

    def refresh(self) -> None:
        self.roles.refresh()


class ParametersPage(StepPage):
    def __init__(self, view: GuidedView, step: ParametersStep) -> None:
        super().__init__(view, step)
        row = QHBoxLayout()
        settings = Card(self.tr("Settings"))
        self.device_form = ParameterForm()
        self.device_form.edited.connect(self._device_edit)
        self.experiment_form = ParameterForm()
        self.experiment_form.edited.connect(self._experiment_edit)
        settings.body.addWidget(self.device_form)
        settings.body.addWidget(self.experiment_form)
        settings.body.addStretch()
        row.addWidget(settings, 1)
        live = Card(self.tr("Live reading"))
        self.big = QLabel("—")
        self.big.setFont(scaled_font(self.font(), 2.2, bold=True))
        self.details = muted(QLabel())
        self.check = QLabel()
        self.check.setWordWrap(True)
        live.body.addWidget(self.big)
        live.body.addWidget(self.details)
        live.body.addWidget(self.check)
        live.body.addStretch()
        row.addWidget(live, 1)
        self.layout_.addLayout(row)
        self.layout_.addStretch()

    def _device_key(self) -> str | None:
        return self.host.role_key(self.step.role)

    def refresh(self) -> None:
        key = self._device_key()
        if key:
            snap = self.host.manager.snapshot(key)
            wanted = [p for p in snap.parameters if p.key in self.step.keys]
            self.device_form.set_parameters(wanted, snap.values)
        exp = self.host.experiment
        self.experiment_form.set_parameters([p for p in exp.params.definitions() if p.key in self.step.experiment_keys],
                                            exp.params.values())
        self.live_changed()

    def live_changed(self) -> None:
        key = self._device_key()
        values = self.host.live.get(key, {}) if key else {}
        loc = QLocale()
        if "lux" in values:
            self.big.setText(f"{loc.toString(float(values['lux']), 'f', 1)} lx")
            self.details.setText(self.tr("{0} counts full spectrum, {1} infrared").format(
                loc.toString(int(values.get("ch0", 0))), loc.toString(int(values.get("ch1", 0)))))
        problem = getattr(self.host.experiment, self.step.check)(values) if self.step.check else None
        self.check.setText(problem or self.tr("Good: a strong reading, below saturation."))
        set_role(self.check, "role", "error" if problem else "muted")

    def _device_edit(self, param: str, value: object) -> None:
        key = self._device_key()
        if key:
            future = self.host.manager.submit(key, "set_parameter", param, value)
            self.host.bridge.watch(future, lambda _v: self.refresh(),
                                   lambda exc: (self.message(error_text(exc), error=True), self.refresh()))

    def _experiment_edit(self, param: str, value: object) -> None:
        future = self.host.runner.call(self.host.experiment.set_parameter, param, value)
        self.host.bridge.watch(future, lambda _v: self.view.refresh(),
                               lambda exc: (self.message(error_text(exc), error=True), self.refresh()))


class InstructionPage(StepPage):
    def __init__(self, view: GuidedView, step: InstructionStep) -> None:
        super().__init__(view, step)
        hint = muted(QLabel(self.tr("When you are ready, press Next.")))
        self.layout_.addWidget(hint)
        self.layout_.addStretch()


class ActionPage(StepPage):
    def __init__(self, view: GuidedView, step: ActionStep) -> None:
        super().__init__(view, step)
        self.button = primary(QPushButton(_(step.button) or _(step.title)))
        self.button.clicked.connect(self._run)
        self.result = QLabel()
        self.result.setFont(scaled_font(self.font(), 1.4, bold=True))
        row = QHBoxLayout()
        row.addWidget(self.button)
        row.addStretch()
        self.layout_.addLayout(row)
        self.layout_.addWidget(self.result)
        self.layout_.addStretch()

    def _run(self) -> None:
        self.message(self.tr("Measuring…"))
        self.host.run(self.step.action, on_ok=lambda _r: (self.message(""), self.view.refresh()),
                      on_error=lambda exc: self.message(error_text(exc), error=True))

    def refresh(self) -> None:
        text = getattr(self.host.experiment, self.step.result)() if self.step.result else ""
        self.result.setText(text)


class TablePage(StepPage):
    def __init__(self, view: GuidedView, step: TableStep) -> None:
        super().__init__(view, step)
        entry = QHBoxLayout()
        self.label = QLabel()
        self.input = QLineEdit()
        self.input.setMaximumWidth(220)
        self.input.returnPressed.connect(self._measure)
        self.button = primary(QPushButton(_(step.button) or self.tr("Measure")))
        self.button.clicked.connect(self._measure)
        entry.addWidget(self.label)
        entry.addWidget(self.input)
        entry.addWidget(self.button)
        entry.addStretch()
        if step.dataset == "standards" and hasattr(self.host.experiment, "apply_calibration"):
            reuse = QPushButton(self.tr("Use a saved calibration…"))
            reuse.clicked.connect(self._reuse_calibration)
            entry.addWidget(reuse)
        self.layout_.addLayout(entry)
        split = QSplitter()
        table_card = Card(self.tr("Measurements"))
        self.table = DatasetTable()
        table_card.body.addWidget(self.table)
        if step.remove_action:
            remove = QPushButton(self.tr("Remove selected row"))
            remove.clicked.connect(self._remove)
            table_card.body.addWidget(remove)
        split.addWidget(table_card)
        if step.plot:
            plot_card = Card(self.tr("Graph"))
            self.plot = PlotView()
            plot_card.body.addWidget(self.plot, 1)
            self.summary = QLabel()
            self.summary.setWordWrap(True)
            plot_card.body.addWidget(self.summary)
            split.addWidget(plot_card)
        self.layout_.addWidget(split, 1)

    def refresh(self) -> None:
        exp = self.host.experiment
        unit = exp.params[self.step.input_unit_parameter] if self.step.input_unit_parameter else ""
        self.label.setText(_(self.step.input_label) + (f" ({unit})" if unit else ""))
        self.table.show_dataset(exp.session.datasets[self.step.dataset])
        if self.step.plot:
            self.plot.show_data(getattr(exp, self.step.plot)())
            self.summary.setText(getattr(exp, self.step.summary)() if self.step.summary else "")

    def _measure(self) -> None:
        text = self.input.text().strip()
        if self.step.input_kind == "float":
            try:
                value: object = parse_number(text)
            except ValueError:
                self.message(self.tr("Type a number, for example 0.02."), error=True)
                return
        else:
            value = text
        self.button.setEnabled(False)
        self.message(self.tr("Measuring…"))

        def ok(_result: object) -> None:
            self.button.setEnabled(True)
            self.input.clear()
            self.input.setFocus()
            self.message("")
            self.view.refresh()

        def failed(exc: BaseException) -> None:
            self.button.setEnabled(True)
            self.message(error_text(exc), error=True)

        self.host.run(self.step.row_action, value, on_ok=ok, on_error=failed)

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self.message(self.tr("Select a row first."), error=True)
            return
        self.host.run(self.step.remove_action, row, on_ok=lambda _r: self.view.refresh(),
                      on_error=lambda exc: self.message(error_text(exc), error=True))

    def _reuse_calibration(self) -> None:
        library = self.host.calibrations()
        found = library.list() if library else []
        if not found:
            self.message(self.tr("No saved calibrations yet."), error=True)
            return
        names = [f"{c.label} · {c.created[:16].replace('T', ' ')}" for c in found]
        choice, ok = QInputDialog.getItem(self, self.tr("Use a saved calibration"), self.tr("Calibration"), names,
                                          0, False)
        if not ok:
            return
        cal = found[names.index(choice)]

        def applied(differences: dict) -> None:
            text = self.tr("Calibration “{0}” loaded. Measure the blank again before the unknowns.").format(cal.label)
            if differences:
                changed = ", ".join(f"{k}: {then} → {now}" for k, (then, now) in differences.items())
                text += " " + self.tr("Settings restored to the calibration's: {0}.").format(changed)
            self.message(text)
            self.view.refresh()

        future = self.host.runner.call(self.host.experiment.apply_calibration, cal)
        self.host.bridge.watch(future, applied, lambda exc: self.message(error_text(exc), error=True))


class ResultPage(StepPage):
    def __init__(self, view: GuidedView, step: ResultStep) -> None:
        super().__init__(view, step)
        card = Card(self.tr("Results"))
        self.form = QFormLayout()
        card.body.addLayout(self.form)
        self.layout_.addWidget(card)
        buttons = QHBoxLayout()
        save = primary(QPushButton(self.tr("Save session…")))
        save.clicked.connect(lambda: self.host.save_session())
        buttons.addWidget(save)
        if hasattr(self.host.experiment, "save_calibration"):
            cal = QPushButton(self.tr("Save calibration…"))
            cal.clicked.connect(self._save_calibration)
            buttons.addWidget(cal)
        buttons.addStretch()
        self.layout_.addLayout(buttons)
        self.expert_next_time = QCheckBox(self.tr("Next time, open this experiment in expert mode"))
        self.expert_next_time.setChecked(True)
        self.expert_next_time.toggled.connect(
            lambda on: self.host.remember_mode("expert" if on else "guided"))
        self.layout_.addWidget(self.expert_next_time)
        self.layout_.addStretch()

    def refresh(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        loc = QLocale()
        for label, value in self.host.experiment.summary():
            text = QLabel(format_value(value, loc) if isinstance(value, float) else str(value))
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.form.addRow(muted(QLabel(label)), text)
        if self.expert_next_time.isChecked():
            self.host.remember_mode("expert")

    def _save_calibration(self) -> None:
        exp = self.host.experiment
        label, ok = QInputDialog.getText(self, self.tr("Save calibration"), self.tr("Name"),
                                         text=exp.params.values().get("solution", ""))
        if not ok:
            return
        self.host.run("save_calibration", label, on_ok=lambda path: self.message(
            self.tr("Calibration saved: {0}").format(path.name)),
            on_error=lambda exc: self.message(error_text(exc), error=True))


PAGES = {DevicesStep: DevicesPage, ParametersStep: ParametersPage, InstructionStep: InstructionPage,
         ActionStep: ActionPage, TableStep: TablePage, ResultStep: ResultPage}


class GuidedView(QWidget):
    def __init__(self, host: ExperimentHost) -> None:
        super().__init__()
        self.host = host
        self.steps = host.experiment.wizard()
        self.index = min(host.experiment.session.wizard_step, max(0, len(self.steps) - 1))
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.rail = QListWidget()
        self.rail.setFixedWidth(220)
        self.rail.itemClicked.connect(lambda item: self.go(self.rail.row(item)))
        outer.addWidget(self.rail)
        right = QVBoxLayout()
        self.header = PageHeader()
        right.addWidget(self.header)
        self.pages = QStackedWidget()
        self.page_list = [PAGES[type(step)](self, step) for step in self.steps]
        for page in self.page_list:
            self.pages.addWidget(page)
        right.addWidget(self.pages, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        right.addWidget(self.message)
        footer = QHBoxLayout()
        self.back = QPushButton(self.tr("← Back"))
        self.back.clicked.connect(lambda: self.go(self.index - 1))
        self.progress = muted(QLabel())
        self.next = primary(QPushButton(self.tr("Next →")))
        self.next.clicked.connect(lambda: self.go(self.index + 1))
        footer.addWidget(self.back)
        footer.addStretch()
        footer.addWidget(self.progress)
        footer.addStretch()
        footer.addWidget(self.next)
        right.addLayout(footer)
        outer.addLayout(right, 1)
        host.events.changed.connect(self.refresh)
        host.events.busy.connect(lambda busy: self.next.setEnabled(not busy and self._complete(self.index)))
        self.go(self.index)

    def _complete(self, i: int) -> bool:
        step = self.steps[i]
        live = {}
        if isinstance(step, ParametersStep) and (key := self.host.role_key(step.role)):
            live = self.host.live.get(key, {})
        return self.host.experiment.step_complete(step, live)

    def reachable(self, i: int) -> bool:
        return all(self._complete(j) for j in range(i))

    def go(self, i: int) -> None:
        if not self.steps or not 0 <= i < len(self.steps) or (i > self.index and not self.reachable(i)):
            return
        self.index = i
        self.host.experiment.session.wizard_step = i
        self.pages.setCurrentIndex(i)
        self.show_message("")
        self.refresh()

    def refresh(self) -> None:
        if not self.steps:
            return
        step = self.steps[self.index]
        self.header.set_text(_(step.title), _(step.text))
        self.page_list[self.index].refresh()
        self.rail.blockSignals(True)
        self.rail.clear()
        for i, s in enumerate(self.steps):
            mark = "✓" if self._complete(i) and i != len(self.steps) - 1 else str(i + 1)
            item = QListWidgetItem(f"{mark}   {_(s.title)}")
            if i > self.index and not self.reachable(i):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.rail.addItem(item)
        self.rail.setCurrentRow(self.index)
        self.rail.blockSignals(False)
        self.back.setEnabled(self.index > 0)
        last = self.index == len(self.steps) - 1
        self.next.setVisible(not last)
        self.next.setEnabled(self._complete(self.index))
        self.progress.setText(self.tr("Step {0} of {1}").format(self.index + 1, len(self.steps)))

    def devices_changed(self) -> None:
        if self.steps:
            self.refresh()

    def live_changed(self) -> None:
        page = self.page_list[self.index] if self.steps else None
        if isinstance(page, ParametersPage):
            page.live_changed()
            self.next.setEnabled(self._complete(self.index))

    def show_message(self, text: str, *, error: bool = False) -> None:
        self.message.setText(text)
        set_role(self.message, "role", "error" if error else "muted")
