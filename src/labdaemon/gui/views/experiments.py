"""Experiments: the launcher (mockup 1) and one tab per open experiment (design §7.2)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.device import DeviceState
from labdaemon.core.errors import LabError
from labdaemon.core.i18n import _
from labdaemon.core.manager import DeviceManager
from labdaemon.core.registry import Registry
from labdaemon.core.session import Session
from labdaemon.core.settings import Settings
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.experiment.host import ExperimentHost
from labdaemon.gui.widgets.components import Card, PageHeader, StateDot, muted, primary, set_role


class ExperimentCard(Card):
    def __init__(self, view: ExperimentsView, experiment_cls: type) -> None:
        super().__init__()
        self.view = view
        self.cls = experiment_cls
        category = set_role(QLabel(view.category_label(experiment_cls.category).upper()), "role", "section")
        self.body.addWidget(category)
        title = QLabel(_(experiment_cls.name))
        title.setFont(view.title_font)
        title.setWordWrap(True)
        self.body.addWidget(title)
        text = muted(QLabel(_(experiment_cls.description)))
        text.setWordWrap(True)
        self.body.addWidget(text)
        self.requirements = QVBoxLayout()
        self.body.addLayout(self.requirements)
        self.body.addStretch()
        foot = QHBoxLayout()
        self.mode = muted(QLabel())
        foot.addWidget(self.mode)
        foot.addStretch()
        button = primary(QPushButton(self.tr("Open")))
        button.clicked.connect(lambda: view.open_experiment(experiment_cls))
        foot.addWidget(button)
        self.body.addLayout(foot)
        self.refresh()

    def refresh(self) -> None:
        while self.requirements.count():
            item = self.requirements.takeAt(0)
            if item.layout():
                while item.layout().count():
                    item.layout().takeAt(0).widget().deleteLater()
        for req in self.cls.requires.values():
            keys = self.view.manager.devices_providing(req.capability)
            row = QHBoxLayout()
            dot = StateDot()
            dot.set_state(DeviceState.READY if keys else DeviceState.DISCONNECTED)
            names = ", ".join(self.view.device_name(k) for k in keys) or self.tr("not connected")
            row.addWidget(dot)
            label = QLabel(f"{_(req.label)} · {names}")
            label.setWordWrap(True)
            row.addWidget(label, 1)
            self.requirements.addLayout(row)
        mode = self.view.settings.get(f"experiments.{self.cls.id}.mode", "guided")
        self.mode.setText(self.tr("opens in expert mode") if mode == "expert" else self.tr("opens guided"))


class ExperimentsView(QTabWidget):
    def __init__(self, registry: Registry, manager: DeviceManager, bridge: QtBridge, settings: Settings,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.registry = registry
        self.manager = manager
        self.bridge = bridge
        self.settings = settings
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self.title_font = self.font()
        self.title_font.setPointSizeF(self.title_font.pointSizeF() * 1.2)
        self.title_font.setBold(True)

        launcher = QWidget()
        v = QVBoxLayout(launcher)
        head = QHBoxLayout()
        head.addWidget(PageHeader(self.tr("Experiments"),
                                  self.tr("Choose an experiment. Its devices are checked for you.")), 1)
        open_session = QPushButton(self.tr("Open session…"))
        open_session.clicked.connect(lambda: self.open_session())
        head.addWidget(open_session)
        v.addLayout(head)
        self.message = muted(QLabel(self.tr("No experiment plugins are installed yet. You can already connect "
                                            "devices and watch their readings in Devices.")))
        self.message.setWordWrap(True)
        v.addWidget(self.message)
        grid_host = QWidget()
        self.grid = QGridLayout(grid_host)
        self.grid.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidget(grid_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        v.addWidget(scroll, 1)
        self.addTab(launcher, self.tr("All experiments"))
        self.tabBar().setTabButton(0, self.tabBar().ButtonPosition.RightSide, None)
        self.cards: list[ExperimentCard] = []
        self.hosts: list[ExperimentHost] = []
        self._fill()
        bridge.boards_changed.connect(self._refresh_cards)

    def category_label(self, category: str) -> str:
        names = {"chemistry": self.tr("Chemistry"), "physics": self.tr("Physics"), "general": self.tr("General")}
        return names.get(category, category)

    def device_name(self, key: str) -> str:
        try:
            snap = self.manager.snapshot(key)
        except LabError:
            return key
        return snap.board.name

    def _fill(self) -> None:
        experiments = sorted(self.registry.experiments().values(), key=lambda c: (c.category, _(c.name)))
        self.message.setVisible(not experiments)
        for i, cls in enumerate(experiments):
            card = ExperimentCard(self, cls)
            card.setMinimumWidth(300)
            self.cards.append(card)
            self.grid.addWidget(card, i // 3, i % 3)
        self.grid.setRowStretch(len(experiments) // 3 + 1, 1)

    def _refresh_cards(self) -> None:
        for card in self.cards:
            card.refresh()

    # ── tabs ──
    def open_experiment(self, cls: type, session: Session | None = None) -> ExperimentHost:
        host = ExperimentHost.open(cls, self.manager, self.bridge, self.settings, session)
        host.closed.connect(self._host_closed)
        self.hosts.append(host)
        index = self.addTab(host, _(cls.name))
        self.setCurrentIndex(index)
        return host

    def open_session(self, path: Path | None = None) -> ExperimentHost | None:
        if path is None:
            folder = ExperimentHost.sessions_folder_for(self.settings)
            chosen, _filter = QFileDialog.getOpenFileName(self, self.tr("Open session"), str(folder),
                                                          self.tr("LabDaemon sessions (*.labint)"))
            if not chosen:
                return None
            path = Path(chosen)
        try:
            session = Session.load(path)
        except LabError as e:
            QMessageBox.warning(self, self.tr("Open session"), e.message)
            return None
        cls = self.registry.experiment(session.experiment_id)
        if cls is None:
            QMessageBox.warning(self, self.tr("Open session"),
                                self.tr("This session needs the experiment plugin “{0}”, which is not installed.")
                                .format(session.experiment_id))
            return None
        host = self.open_experiment(cls, session)
        host.saved_path = path
        host.dirty = False
        return host

    def _close_tab(self, index: int) -> None:
        widget = self.widget(index)
        if isinstance(widget, ExperimentHost):
            widget.close_experiment()

    def _host_closed(self, host: ExperimentHost) -> None:
        index = self.indexOf(host)
        if index >= 0:
            self.removeTab(index)
        self.hosts.remove(host)
        host.deleteLater()
        self._refresh_cards()

    def close_all(self) -> bool:
        return all(host.close_experiment() for host in list(self.hosts))

