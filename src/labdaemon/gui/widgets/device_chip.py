"""Status-bar chip for a board: a coloured dot, its name, link and state (in words, not only colour)."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from labdaemon.core.device import STATE_LABELS, DeviceState
from labdaemon.core.i18n import _

STATE_COLORS = {
    DeviceState.READY: "#2B8A52",
    DeviceState.BUSY: "#1C5DA6",
    DeviceState.CONNECTING: "#A87300",
    DeviceState.ERROR: "#C23A3A",
    DeviceState.LOST: "#C23A3A",
    DeviceState.DISCONNECTED: "#8A938F",
}


class DeviceChip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(6)
        self.dot = QLabel()
        self.dot.setFixedSize(9, 9)
        self.text = QLabel()
        lay.addWidget(self.dot)
        lay.addWidget(self.text)

    def set_board(self, name: str, link: str, state: DeviceState) -> None:
        self.dot.setStyleSheet(f"background:{STATE_COLORS[state]}; border-radius:4px;")
        self.text.setText(f"{name} · {link} · {_(STATE_LABELS[state]).lower()}")
