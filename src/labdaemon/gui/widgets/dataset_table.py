"""A read-only table showing a Dataset, numbers formatted for the interface language."""

import math

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from labdaemon.core.data import Dataset
from labdaemon.core.i18n import _


def format_value(value: object, locale: QLocale | None = None) -> str:
    loc = locale or QLocale()
    if isinstance(value, float):
        if math.isnan(value):
            return "—"
        magnitude = abs(value)
        decimals = 1 if magnitude >= 100 else 3 if magnitude >= 1 else 4
        return loc.toString(value, "f", decimals)
    return str(value)


class DatasetTable(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verticalHeader().setDefaultSectionSize(24)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def show_dataset(self, dataset: Dataset) -> None:
        rows = dataset.rows()
        headers = [f"{_(c.heading)} ({_(c.unit)})" if c.unit else _(c.heading) for c in dataset.channels]
        selected = self.currentRow()
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        for i, c in enumerate(dataset.channels):
            self.horizontalHeaderItem(i).setToolTip(_(c.label))
        self.setRowCount(len(rows))
        loc = QLocale()
        for r, row in enumerate(rows):
            for c, key in enumerate(dataset.keys):
                item = QTableWidgetItem(format_value(row[key], loc))
                if isinstance(row[key], float):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(r, c, item)
        if 0 <= selected < len(rows):
            self.selectRow(selected)
        elif rows:
            self.scrollToBottom()
