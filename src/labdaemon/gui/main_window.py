"""Main window: navigation rail, the pages, and a status bar with one chip per board."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.board import link_label
from labdaemon.core.device import DeviceState
from labdaemon.core.manager import DeviceManager
from labdaemon.core.registry import Registry
from labdaemon.core.settings import Settings
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.icons import icon
from labdaemon.gui.views.devices import DevicesView
from labdaemon.gui.views.experiments import ExperimentsView
from labdaemon.gui.views.plugins import PluginsView
from labdaemon.gui.views.settings import SettingsView
from labdaemon.gui.widgets.device_chip import DeviceChip

# worst first: a board chip shows the most urgent state among its devices
_SEVERITY = [DeviceState.LOST, DeviceState.ERROR, DeviceState.CONNECTING, DeviceState.BUSY,
             DeviceState.READY, DeviceState.DISCONNECTED]


class MainWindow(QMainWindow):
    def __init__(self, manager: DeviceManager, registry: Registry, settings: Settings,
                 bridge: QtBridge) -> None:
        super().__init__()
        self.manager = manager
        self.setWindowTitle("LabDaemon")
        self.resize(1200, 780)

        self.experiments = ExperimentsView()
        self.devices = DevicesView(manager, bridge)
        self.plugins = PluginsView(registry, manager, settings.paths.user_plugins)
        self.settings_view = SettingsView(settings)
        self.stack = QStackedWidget()

        rail = QWidget()
        rail.setObjectName("rail")
        rail.setFixedWidth(108)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(6, 8, 6, 8)
        rv.setSpacing(2)
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        pages = [("experiments", self.tr("Experiments"), self.experiments),
                 ("devices", self.tr("Devices"), self.devices),
                 ("plugins", self.tr("Plugins"), self.plugins),
                 (None, None, None),
                 ("settings", self.tr("Settings"), self.settings_view)]
        color = self.palette().text().color()
        for name, label, page in pages:
            if name is None:
                rv.addStretch()
                continue
            button = QToolButton()
            button.setText(label)
            button.setIcon(icon(name, color))
            button.setIconSize(QSize(22, 22))
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setSizePolicy(button.sizePolicy().horizontalPolicy(), button.sizePolicy().verticalPolicy())
            button.setMinimumWidth(96)
            self.stack.addWidget(page)
            button.clicked.connect(lambda _c=False, page=page: self.show_page(page))
            self.nav.addButton(button)
            button.setProperty("page", page)
            rv.addWidget(button)
        rail.setStyleSheet(
            "#rail { border-right: 1px solid palette(mid); }"
            "#rail QToolButton { border: none; border-radius: 6px; padding: 6px 2px; }"
            "#rail QToolButton:checked { background: palette(highlight); color: palette(highlighted-text); }")

        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(rail)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._chips: dict[str, DeviceChip] = {}
        bridge.boards_changed.connect(self._rebuild_chips)
        bridge.device_state.connect(lambda *_: self._update_chips())
        bridge.boards_changed.connect(self.plugins.refresh)
        self.show_page(self.devices)

    def show_page(self, page: QWidget) -> None:
        self.stack.setCurrentWidget(page)
        for button in self.nav.buttons():
            button.setChecked(button.property("page") is page)

    def _rebuild_chips(self) -> None:
        for chip in self._chips.values():
            self.statusBar().removeWidget(chip)
            chip.deleteLater()
        self._chips = {}
        for board in self.manager.boards():
            chip = DeviceChip()
            self.statusBar().addWidget(chip)
            chip.show()
            self._chips[board.key] = chip
        self._update_chips()

    def _update_chips(self) -> None:
        for board in self.manager.boards():
            chip = self._chips.get(board.key)
            if chip is None:
                continue
            states = [self.manager.state(d.key) for d in board.devices.values()] or [DeviceState.READY]
            worst = min(states, key=_SEVERITY.index)
            chip.set_board(board.name, link_label(board.address.link), worst)

    def closeEvent(self, event) -> None:
        self.manager.shutdown()
        super().closeEvent(event)
