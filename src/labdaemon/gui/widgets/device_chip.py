"""Status-bar chip for a board: a coloured dot, its name, link and state (in words, not only colour)."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from labdaemon.core.device import STATE_LABELS, DeviceState
from labdaemon.core.i18n import _
from labdaemon.gui.widgets.components import StateDot


class DeviceChip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 10, 0)
        lay.setSpacing(6)
        self.dot = StateDot()
        self.text = QLabel()
        lay.addWidget(self.dot)
        lay.addWidget(self.text)

    def set_board(self, name: str, link: str, state: DeviceState) -> None:
        self.dot.set_state(state)
        self.text.setText(f"{name} · {link} · {_(STATE_LABELS[state]).lower()}")
