"""Experiments view (the launcher of mockup 1 arrives in M1, with the first experiments)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExperimentsView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        title = QLabel(self.tr("Experiments"))
        title.setStyleSheet("font-weight:600; font-size:15pt;")
        v.addWidget(title)
        self.message = QLabel(self.tr("No experiment plugins are installed yet. You can already connect devices "
                                      "and watch their readings in Devices."))
        self.message.setWordWrap(True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignTop)
        v.addWidget(self.message)
        v.addStretch()
