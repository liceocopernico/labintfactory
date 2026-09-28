"""Add device: boards found on USB, plus the simulated twins of the device plugins (mockup 3, USB part)."""

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labdaemon.core.errors import LabError
from labdaemon.core.i18n import _
from labdaemon.core.manager import DeviceManager, ScanResult
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.widgets.components import PageHeader, muted, primary, set_role

_ROLE = Qt.ItemDataRole.UserRole


class AddDeviceDialog(QDialog):
    def __init__(self, manager: DeviceManager, bridge: QtBridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.bridge = bridge
        self._pool = ThreadPoolExecutor(1, thread_name_prefix="add-device")
        self.setWindowTitle(self.tr("Add device"))
        self.resize(820, 420)
        v = QVBoxLayout(self)
        v.addWidget(PageHeader(self.tr("Add device"),
                               self.tr("LabInt boards found on USB, and simulated devices for trying LabDaemon "
                                       "without hardware.")))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([self.tr("Where"), self.tr("Board"), self.tr("Functions"),
                                              self.tr("Status")])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda _item: self._connect())
        v.addWidget(self.table, 1)
        self.message = muted(QLabel())
        self.message.setWordWrap(True)
        v.addWidget(self.message)
        buttons = QHBoxLayout()
        self.rescan = QPushButton(self.tr("Search again"))
        self.rescan.clicked.connect(self.scan)
        buttons.addWidget(self.rescan)
        buttons.addStretch()
        cancel = QPushButton(self.tr("Close"))
        cancel.clicked.connect(self.reject)
        self.connect_button = primary(QPushButton(self.tr("Connect")))
        self.connect_button.clicked.connect(self._connect)
        buttons.addWidget(cancel)
        buttons.addWidget(self.connect_button)
        v.addLayout(buttons)
        self.connected_key: str | None = None
        self.scan()

    # ── rows ──
    def scan(self) -> None:
        self.rescan.setEnabled(False)
        self._show_message(self.tr("Searching USB ports…"))
        self._fill([])
        self.bridge.watch(self._pool.submit(self.manager.scan_serial), self._scanned,
                          lambda exc: self._show_message(str(exc), error=True))

    def _scanned(self, results: list[ScanResult]) -> None:
        self.rescan.setEnabled(True)
        self._fill(results)
        boards = sum(1 for r in results if r.info)
        self._show_message(self.tr("{0} USB port(s), {1} LabInt board(s).").format(len(results), boards)
                           if results else self.tr("No USB serial ports found. Is the board plugged in?"))

    def _fill(self, results: list[ScanResult]) -> None:
        rows: list[tuple[list[str], dict | None]] = []
        for r in results:
            if r.info:
                fns = ", ".join(fn if pid else self.tr("{0} (no plugin)").format(fn) for fn, pid in r.plugins.items())
                status = self.tr("connected") if r.connected else (
                    self.tr("ready") if any(r.plugins.values()) else self.tr("no plugin for these functions"))
                action = None if r.connected or not any(r.plugins.values()) else {"serial": r.port.device}
                rows.append(([f"USB {r.port.device}", f"{r.info.name} · {r.info.board} · fw {r.info.firmware}",
                              fns, status], action))
            else:
                rows.append(([f"USB {r.port.device}", r.port.description, "—",
                              self.tr("not a LabInt board ({0})").format(r.error)], None))
        for pid, cls in sorted(self.manager.registry.devices().items()):
            if cls.simulated:
                rows.append(([self.tr("simulated"), _(cls.name), ", ".join(sorted(cls.models)),
                              self.tr("for trying without hardware")], {"simulated": pid}))
        self.table.setRowCount(len(rows))
        for row, (cells, action) in enumerate(rows):
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(_ROLE, action)
                if action is None:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        first = next((r for r in range(len(rows)) if rows[r][1] and "serial" in rows[r][1]), None)
        if first is not None:
            self.table.selectRow(first)
        self._update_buttons()

    def _selected(self) -> dict | None:
        items = self.table.selectedItems()
        return items[0].data(_ROLE) if items else None

    def _update_buttons(self) -> None:
        self.connect_button.setEnabled(self._selected() is not None)

    # ── connecting ──
    def _connect(self) -> None:
        action = self._selected()
        if not action:
            return
        self.connect_button.setEnabled(False)
        self._show_message(self.tr("Connecting…"))
        if "serial" in action:
            future = self._pool.submit(self.manager.connect_serial, action["serial"])
        else:
            future = self._pool.submit(self.manager.simulate, action["simulated"])
        self.bridge.watch(future, self._connected, self._failed)

    def _connected(self, board) -> None:
        self.connected_key = next(iter(board.devices.values())).key if board.devices else None
        self.accept()

    def _failed(self, exc: BaseException) -> None:
        self._update_buttons()
        text = exc.message if isinstance(exc, LabError) else str(exc)
        self._show_message(self.tr("Could not connect: {0}").format(text), error=True)

    def _show_message(self, text: str, *, error: bool = False) -> None:
        self.message.setText(text)
        set_role(self.message, "role", "error" if error else "muted")

    def done(self, result: int) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().done(result)
