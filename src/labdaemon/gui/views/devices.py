"""Devices view: connected boards and their functions, settings, live reading and commands."""

import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import pyqtgraph as pg
from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.board import link_label
from labdaemon.core.device import STATE_LABELS, DeviceState
from labdaemon.core.errors import LabError
from labdaemon.core.i18n import _
from labdaemon.core.manager import DeviceManager, DeviceSnapshot
from labdaemon.gui import theme
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.widgets.components import Card, PageHeader, StatePill, muted, scaled_font, set_role
from labdaemon.gui.widgets.parameter_form import ParameterForm

HISTORY_SECONDS = 60
_KEY_ROLE = Qt.ItemDataRole.UserRole


def error_text(exc: BaseException) -> str:
    return exc.message if isinstance(exc, LabError) else str(exc) or type(exc).__name__


class DevicesView(QWidget):
    def __init__(self, manager: DeviceManager, bridge: QtBridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.bridge = bridge
        self._connector = ThreadPoolExecutor(1, thread_name_prefix="connect")
        self._history: dict[str, deque[tuple[float, dict]]] = {}

        # left: boards and their functions
        left = QWidget()
        lv = QVBoxLayout(left)
        head = QHBoxLayout()
        title = set_role(QLabel(self.tr("Boards")), "role", "section")
        head.addWidget(title)
        head.addStretch()
        self.add_button = QToolButton()
        self.add_button.setText(self.tr("Add simulated device"))
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        set_role(self.add_button, "role", "menu-button")
        self.add_menu = QMenu(self.add_button)
        self.add_button.setMenu(self.add_menu)
        head.addWidget(self.add_button)
        lv.addLayout(head)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(lambda *_: self._select_current())
        lv.addWidget(self.tree, 1)
        self.disconnect_button = QPushButton(self.tr("Disconnect board"))
        self.disconnect_button.clicked.connect(self._disconnect_current)
        lv.addWidget(self.disconnect_button)

        # right: details of the selected device, or an empty state
        self.detail = DeviceDetail(self)
        self.detail.form.edited.connect(self._edit)
        self.empty = muted(QLabel(self.tr("No device selected.\n\nConnect a board, or add a simulated device to try "
                                          "LabDaemon without hardware.")))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.right = QStackedWidget()
        self.right.addWidget(self.empty)
        self.right.addWidget(self.detail)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.right)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 800])
        outer = QHBoxLayout(self)
        outer.addWidget(split)

        bridge.boards_changed.connect(self._rebuild_tree)
        bridge.device_state.connect(self._on_state)
        bridge.sample.connect(self._on_sample)
        bridge.parameters_changed.connect(self._on_parameters_changed)
        bridge.error.connect(self._on_error)
        self._fill_add_menu()
        theme.on_change(self._rebuild_tree)

    # ── connecting ──
    def _fill_add_menu(self) -> None:
        self.add_menu.clear()
        simulated = {pid: cls for pid, cls in self.manager.registry.devices().items() if cls.simulated}
        for pid, cls in simulated.items():
            action = self.add_menu.addAction(_(cls.name))
            action.triggered.connect(lambda _checked=False, pid=pid: self.add_simulated(pid))
        self.add_button.setEnabled(bool(simulated))

    def add_simulated(self, plugin_id: str) -> None:
        self.detail.show_message(self.tr("Connecting…"))
        future = self._connector.submit(self.manager.simulate, plugin_id)
        self.bridge.watch(future, lambda board: self._select_board(board.key),
                          lambda exc: self._show_error(self.tr("Could not connect: {0}").format(error_text(exc))))

    def _disconnect_current(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        key = item.data(0, _KEY_ROLE) or ""
        self._connector.submit(self.manager.disconnect, key.partition("/")[0])

    # ── tree ──
    def _rebuild_tree(self) -> None:
        current = self.current_key()
        self.tree.blockSignals(True)
        self.tree.clear()
        for board in self.manager.boards():
            info = board.info
            top = QTreeWidgetItem([f"{board.name}   ·   {info.board} · {link_label(board.address.link)}"])
            top.setData(0, _KEY_ROLE, board.key)
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            self.tree.addTopLevelItem(top)
            for dev in board.devices.values():
                child = QTreeWidgetItem([_(dev.name)])
                child.setData(0, _KEY_ROLE, dev.key)
                top.addChild(child)
                self._paint_state(child, self.manager.state(dev.key))
            for fn in board.unsupported:
                child = QTreeWidgetItem([self.tr("{0}: no plugin installed").format(fn)])
                child.setDisabled(True)
                top.addChild(child)
            top.setExpanded(True)
        self.tree.blockSignals(False)
        self._select_key(current)
        self.disconnect_button.setEnabled(bool(self.manager.boards()))
        self._select_current()

    def _paint_state(self, item: QTreeWidgetItem, state: DeviceState) -> None:
        item.setToolTip(0, _(STATE_LABELS[state]))
        color = theme.state_color(state) if state != DeviceState.READY else theme.tokens().ink
        item.setForeground(0, QColor(color))

    def _select_board(self, board_key: str) -> None:
        board = next((b for b in self.manager.boards() if b.key == board_key), None)
        if board and board.devices:
            self._select_key(next(iter(board.devices.values())).key)

    def _select_key(self, key: str | None) -> None:
        if not key:
            return
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, _KEY_ROLE) == key:
                    self.tree.setCurrentItem(top.child(j))
                    return

    def current_key(self) -> str | None:
        item = self.tree.currentItem()
        key = item.data(0, _KEY_ROLE) if item else None
        return key if key and "/" in key else None

    def _select_current(self) -> None:
        key = self.current_key()
        if key is None:
            self.right.setCurrentWidget(self.empty)
            return
        try:
            snap = self.manager.snapshot(key)
        except LabError:
            self.right.setCurrentWidget(self.empty)
            return
        self.detail.show_device(snap, self._history.get(key, ()))
        self.detail.command_clicked = lambda cmd, key=key: self._run_command(key, cmd)
        self.right.setCurrentWidget(self.detail)

    # ── live updates ──
    def _on_state(self, key: str, state: str) -> None:
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, _KEY_ROLE) == key:
                    self._paint_state(top.child(j), DeviceState(state))
        if key == self.current_key():
            self.detail.show_state(DeviceState(state))

    def _on_sample(self, key: str, values: dict, t: float) -> None:
        history = self._history.setdefault(key, deque())
        history.append((t, values))
        while history and history[0][0] < t - HISTORY_SECONDS:
            history.popleft()
        if key == self.current_key():
            self.detail.show_sample(values, history)

    def _on_parameters_changed(self, key: str) -> None:
        if key == self.current_key():
            snap = self.manager.snapshot(key)
            self.detail.form.set_parameters(snap.parameters, snap.values)

    def _on_error(self, key: str, exc: object) -> None:
        if key == self.current_key() and isinstance(exc, BaseException):
            self._show_error(error_text(exc))

    # ── editing ──
    def _edit(self, param: str, value: object) -> None:
        key = self.current_key()
        if key is None:
            return
        future = self.manager.submit(key, "set_parameter", param, value)
        self.bridge.watch(future, lambda _values: self.detail.show_message(""),
                          lambda exc: self._revert_after_error(key, exc))

    def _revert_after_error(self, key: str, exc: BaseException) -> None:
        self._show_error(error_text(exc))
        if key == self.current_key():
            snap = self.manager.snapshot(key)
            self.detail.form.set_parameters(snap.parameters, snap.values)

    def _run_command(self, key: str, command: str) -> None:
        future = self.manager.submit(key, "run_command", command)
        self.bridge.watch(future, lambda msg: self.detail.show_message(msg or ""),
                          lambda exc: self._show_error(error_text(exc)))

    def _show_error(self, text: str) -> None:
        self.detail.show_message(text, error=True)
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(text, 8000)


class DeviceDetail(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.command_clicked = lambda cmd: None
        self._channels = []
        self._value_labels: dict[str, QLabel] = {}
        v = QVBoxLayout(self)
        v.setSpacing(10)

        self.header = PageHeader()
        self.state = StatePill()
        self.header.right.addWidget(self.state, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(self.header)

        body = QHBoxLayout()
        body.setSpacing(10)
        settings_card = Card(self.tr("Settings"))
        self.form = ParameterForm()
        settings_card.body.addWidget(self.form)
        settings_card.body.addStretch()
        body.addWidget(settings_card, 1)

        live_card = Card(self.tr("Live reading"))
        self.big = QLabel("—")
        self.big.setFont(scaled_font(self.font(), 2.4, bold=True))
        live_card.body.addWidget(self.big)
        self.values_grid = QGridLayout()
        self.values_grid.setHorizontalSpacing(16)
        live_card.body.addLayout(self.values_grid)
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(140)
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", self.tr("seconds ago"))
        self.plot.getPlotItem().getViewBox().setMouseEnabled(x=False, y=False)
        self.curve = self.plot.plot([], [])
        live_card.body.addWidget(self.plot, 1)
        body.addWidget(live_card, 1)
        v.addLayout(body, 1)

        commands_card = Card(self.tr("Commands"))
        self.commands_row = QHBoxLayout()
        commands_card.body.addLayout(self.commands_row)
        v.addWidget(commands_card)

        self.message = QLabel()
        self.message.setWordWrap(True)
        v.addWidget(self.message)
        theme.on_change(self._style_plot)

    def _style_plot(self) -> None:
        theme.style_plot(self.plot)
        self.curve.setPen(theme.series_pen("a"))

    def show_device(self, snap: DeviceSnapshot, history) -> None:
        b = snap.board
        self.header.set_text(
            f"{b.name} · {_(snap.plugin_name)}",
            self.tr("board {board} · {link} · serial {serial} · firmware {fw} · protocol {proto}").format(
                board=b.board, link=link_label(snap.address.link), serial=b.serial, fw=b.firmware, proto=b.proto))
        self.show_state(snap.state)
        self.form.set_parameters(snap.parameters, snap.values)
        self._channels = snap.channels
        while self.values_grid.count():
            self.values_grid.takeAt(0).widget().deleteLater()
        self._value_labels = {}
        for row, ch in enumerate(snap.channels[1:]):
            value = QLabel("—")
            self.values_grid.addWidget(muted(QLabel(_(ch.label))), row, 0)
            self.values_grid.addWidget(value, row, 1)
            self._value_labels[ch.key] = value
        self.values_grid.setColumnStretch(1, 1)
        if snap.channels:
            self.plot.setLabel("left", f"{_(snap.channels[0].label)} ({_(snap.channels[0].unit)})")
        while self.commands_row.count():
            item = self.commands_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for cmd in snap.commands:
            button = QPushButton(_(cmd.label))
            button.setToolTip(_(cmd.help) if cmd.help else "")
            button.clicked.connect(lambda _c=False, key=cmd.key: self.command_clicked(key))
            self.commands_row.addWidget(button)
        self.commands_row.addStretch()
        self.big.setText("—")
        self.curve.setData([], [])
        if history:
            self.show_sample(history[-1][1], history)
        self.show_message("")

    def show_state(self, state: DeviceState) -> None:
        self.state.set_state(state)

    def show_sample(self, values: dict, history) -> None:
        if not self._channels:
            return
        loc = QLocale()
        first = self._channels[0]
        if first.key in values:
            self.big.setText(f"{loc.toString(float(values[first.key]), 'f', 1)} {_(first.unit)}")
        for ch in self._channels[1:]:
            if ch.key in values and ch.key in self._value_labels:
                v = values[ch.key]
                text = loc.toString(int(v)) if ch.unit == "counts" else loc.toString(float(v), "f", 2)
                self._value_labels[ch.key].setText(f"{text} {_(ch.unit)}")
        if values.get("saturated"):
            self.show_message(self.tr("The sensor is saturated: lower the LED power or the gain."), error=True)
        now = time.monotonic()
        xs = [t - now for t, v in history if first.key in v]
        ys = [float(v[first.key]) for t, v in history if first.key in v]
        self.curve.setData(xs, ys)
        self.plot.setXRange(-HISTORY_SECONDS, 0, padding=0)
        if ys:
            # Don't zoom into sensor noise: show at least ±2 % around the mean (or ±1 unit near zero).
            lo, hi = min(ys), max(ys)
            mid, half = (lo + hi) / 2, max((hi - lo) / 2 * 1.1, abs(sum(ys) / len(ys)) * 0.02, 1.0)
            self.plot.setYRange(mid - half, mid + half, padding=0)

    def show_message(self, text: str, *, error: bool = False) -> None:
        self.message.setText(text)
        set_role(self.message, "role", "error" if error else "muted")
