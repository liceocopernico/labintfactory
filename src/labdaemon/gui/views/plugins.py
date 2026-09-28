"""Plugins view: what was found, where it came from, and why a plugin did not load."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.i18n import _
from labdaemon.core.manager import DeviceManager
from labdaemon.core.registry import Registry, Status


class PluginsView(QWidget):
    def __init__(self, registry: Registry, manager: DeviceManager, user_plugins_dir,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.registry = registry
        self.manager = manager
        self.user_plugins_dir = user_plugins_dir
        v = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(self.tr("Plugins"))
        title.setStyleSheet("font-weight:600; font-size:15pt;")
        head.addWidget(title)
        head.addStretch()
        open_folder = QPushButton(self.tr("Open plugin folder"))
        open_folder.clicked.connect(self._open_folder)
        self.reload = QPushButton(self.tr("Reload plugins"))
        self.reload.setToolTip(self.tr("Possible while no board is connected."))
        self.reload.clicked.connect(self._reload)
        head.addWidget(open_folder)
        head.addWidget(self.reload)
        v.addLayout(head)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([self.tr("Plugin"), self.tr("Kind"), self.tr("Source"),
                                              self.tr("Version"), self.tr("API"), self.tr("Status")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v.addWidget(self.table, 1)
        self.folders = QLabel()
        self.folders.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.folders.setWordWrap(True)
        v.addWidget(self.folders)
        self.refresh()

    def refresh(self) -> None:
        records = self.registry.records()
        self.table.setRowCount(len(records))
        kinds = {"device": self.tr("device"), "transport": self.tr("transport"), "experiment": self.tr("experiment")}
        sources = {"built-in": self.tr("built-in"), "folder": self.tr("plugin folder")}
        statuses = {Status.LOADED: self.tr("loaded"), Status.ERROR: self.tr("error"),
                    Status.INCOMPATIBLE: self.tr("incompatible"), Status.OVERRIDDEN: self.tr("overridden"),
                    Status.CONFLICT: self.tr("conflict")}
        for row, r in enumerate(records):
            status = statuses[r.status]
            if r.error:
                status += " — " + r.error.strip().splitlines()[-1]
            cells = [_(r.name), kinds.get(r.kind, r.kind), sources.get(r.source, r.source), r.version,
                     str(r.api), status]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 5 and r.error:
                    item.setToolTip(r.error)
                    item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        dirs = "\n".join(str(d) for d in self.registry.plugin_dirs)
        self.folders.setText(self.tr("Plugin folders, in search order:") + "\n" + dirs)
        self.reload.setEnabled(not self.manager.boards())

    def _open_folder(self) -> None:
        self.user_plugins_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.user_plugins_dir)))

    def _reload(self) -> None:
        if self.manager.boards():
            return
        self.registry.load()
        self.refresh()
