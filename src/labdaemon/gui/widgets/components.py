"""Shared building blocks from the mockups. They carry roles; gui/theme.py decides how roles look."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from labdaemon.core.device import STATE_LABELS, DeviceState
from labdaemon.core.i18n import _
from labdaemon.gui.theme import STATE_TONES


def set_role(widget: QWidget, name: str, value: object) -> QWidget:
    """Set a styling property and make Qt re-read the stylesheet for it."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def muted(label: QLabel) -> QLabel:
    return set_role(label, "role", "muted")


def scaled_font(base: QFont, factor: float, *, bold: bool = False) -> QFont:
    font = QFont(base)
    font.setPointSizeF(base.pointSizeF() * factor)
    font.setBold(bold)
    return font


class StatePill(QLabel):
    """'Ready', 'Busy', 'Error' … in words and colour, like the mockups' pills."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_tone("muted", "")

    def set_state(self, state: DeviceState) -> None:
        self.set_tone(STATE_TONES[state], _(STATE_LABELS[state]))

    def set_tone(self, tone: str, text: str) -> None:
        self.setText(text)
        set_role(self, "pill", tone)


class StateDot(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(9, 9)
        self.set_state(DeviceState.DISCONNECTED)

    def set_state(self, state: DeviceState) -> None:
        set_role(self, "dot", STATE_TONES[state])


class Card(QFrame):
    """A bordered panel with an optional title strip (the mockups' docks). Put content in `body`."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.title = QLabel(title)
        set_role(self.title, "role", "card-title")
        self.title.setVisible(bool(title))
        outer.addWidget(self.title)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(10, 9, 10, 10)
        self.body.setSpacing(7)
        outer.addLayout(self.body, 1)


class PageHeader(QWidget):
    """A page or device title with a muted subtitle and room for widgets on the right."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 4)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = QLabel(title)
        self.title.setFont(scaled_font(self.font(), 1.4, bold=True))
        self.subtitle = muted(QLabel(subtitle))
        self.subtitle.setWordWrap(True)
        self.subtitle.setVisible(bool(subtitle))
        texts.addWidget(self.title)
        texts.addWidget(self.subtitle)
        row.addLayout(texts, 1)
        self.right = QHBoxLayout()
        row.addLayout(self.right)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.subtitle.setVisible(bool(subtitle))


def primary(button: QPushButton) -> QPushButton:
    """Mark the one main action of a screen."""
    return set_role(button, "primary", True)
