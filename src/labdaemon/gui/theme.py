"""The visual theme: design tokens from the mockups (docs/design, "--m-*" tokens), as a Qt palette and
one application stylesheet, in a light and a dark variant.

Rule: views never pick colours or write stylesheets themselves. They use roles and the shared
components in gui/widgets/components.py, and ask this module for colours they must paint in code
(charts, state colours). tests/gui/test_theme.py enforces it.
"""

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from labdaemon.core.device import DeviceState

MODES = ("system", "light", "dark")
RADIUS = 6


@dataclass(frozen=True)
class Tokens:
    name: str
    win: str  # window and card background
    chrome: str  # status bar, title strips
    panel: str  # side panels, card headers, table headers
    field: str  # input fields, chart background
    ink: str  # text
    muted: str  # secondary text
    rule: str  # borders and grid lines
    sel: str  # accent fill: selection, primary buttons
    sel_ink: str  # text on the accent fill
    sel_soft: str  # selected rail item, highlighted rows
    sel_text: str  # accent-coloured text and icons: selected rail item, links, "busy" pills
    ok: str
    warn: str
    err: str
    series: dict[str, str] = field(default_factory=dict)  # chart series: a (main), fit, x, y, z


LIGHT = Tokens(
    name="light",
    win="#FBFBFB", chrome="#E3E7E5", panel="#F1F3F2", field="#FFFFFF",
    ink="#1D2421", muted="#5F6965", rule="#C8CFCC",
    sel="#1C5DA6", sel_ink="#FFFFFF", sel_soft="#DCE6F3", sel_text="#1C5DA6",
    ok="#2B7A4B", warn="#8F6200", err="#B83535",
    series={"a": "#1C5DA6", "fit": "#C8650A", "x": "#C2394B", "y": "#2E8B57", "z": "#1C5DA6"},
)

DARK = Tokens(
    name="dark",
    win="#1E2422", chrome="#2A312E", panel="#232A28", field="#161B1A",
    ink="#E1E7E4", muted="#9CA7A2", rule="#3A4440",
    sel="#2F6DB8", sel_ink="#FFFFFF", sel_soft="#22364F", sel_text="#7DAEF0",
    ok="#5DBE85", warn="#E0B040", err="#EE7A7A",
    series={"a": "#7DAEF0", "fit": "#F0A04B", "x": "#F07A8A", "y": "#62C48C", "z": "#7DAEF0"},
)

# What each device state looks like: a tone of the pill/dot (see stylesheet) and its colour token.
STATE_TONES = {
    DeviceState.READY: "ok",
    DeviceState.BUSY: "info",
    DeviceState.CONNECTING: "warn",
    DeviceState.ERROR: "err",
    DeviceState.LOST: "err",
    DeviceState.DISCONNECTED: "muted",
}


def tone_color(t: Tokens, tone: str) -> str:
    return {"ok": t.ok, "warn": t.warn, "err": t.err, "info": t.sel_text, "muted": t.muted}[tone]


def palette(t: Tokens) -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: t.win, QPalette.ColorRole.WindowText: t.ink,
        QPalette.ColorRole.Base: t.field, QPalette.ColorRole.AlternateBase: t.panel,
        QPalette.ColorRole.Text: t.ink, QPalette.ColorRole.PlaceholderText: t.muted,
        QPalette.ColorRole.Button: t.panel, QPalette.ColorRole.ButtonText: t.ink,
        QPalette.ColorRole.Highlight: t.sel, QPalette.ColorRole.HighlightedText: t.sel_ink,
        QPalette.ColorRole.ToolTipBase: t.win, QPalette.ColorRole.ToolTipText: t.ink,
        QPalette.ColorRole.Link: t.sel_text, QPalette.ColorRole.BrightText: t.err,
        QPalette.ColorRole.Mid: t.rule, QPalette.ColorRole.Midlight: t.panel,
        QPalette.ColorRole.Dark: t.rule, QPalette.ColorRole.Shadow: t.rule,
        QPalette.ColorRole.Light: t.field,
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.muted))
    return p


def stylesheet(t: Tokens) -> str:
    tones = "\n".join(
        f'QLabel[pill="{tone}"] {{ color: {tone_color(t, tone)}; border-color: {tone_color(t, tone)}; }}\n'
        f'QLabel[dot="{tone}"] {{ background: {tone_color(t, tone)}; }}'
        for tone in ("ok", "warn", "err", "info", "muted"))
    return f"""
QToolTip {{ color: {t.ink}; background: {t.win}; border: 1px solid {t.rule}; padding: 4px; }}

/* navigation rail */
#rail {{ background: {t.panel}; border-right: 1px solid {t.rule}; }}
#rail QToolButton {{ border: none; border-radius: {RADIUS}px; padding: 7px 2px 5px 2px; color: {t.muted}; }}
#rail QToolButton:hover {{ background: {t.chrome}; }}
#rail QToolButton:checked {{ background: {t.sel_soft}; color: {t.sel_text}; font-weight: 600; }}

/* status bar */
QStatusBar {{ background: {t.chrome}; border-top: 1px solid {t.rule}; color: {t.muted}; }}
QStatusBar::item {{ border: none; }}

/* cards (the mockups' docks) */
QFrame[card="true"] {{ background: {t.win}; border: 1px solid {t.rule}; border-radius: {RADIUS}px; }}
QLabel[role="card-title"] {{
    background: {t.panel}; color: {t.muted}; font-weight: 600; padding: 5px 10px;
    border: none; border-bottom: 1px solid {t.rule};
    border-top-left-radius: {RADIUS}px; border-top-right-radius: {RADIUS}px; }}

/* text roles */
QLabel[role="muted"] {{ color: {t.muted}; }}
QLabel[role="error"] {{ color: {t.err}; }}
QLabel[role="section"] {{ color: {t.muted}; font-weight: 600; }}

/* state pills and dots */
QLabel[pill] {{ border: 1px solid; border-radius: 9px; padding: 1px 8px; font-weight: 600; background: transparent; }}
QLabel[dot] {{ border-radius: 4px; }}
{tones}

/* buttons */
QPushButton[primary="true"] {{
    background: {t.sel}; color: {t.sel_ink}; border: 1px solid {t.sel}; border-radius: 4px; padding: 5px 14px; }}
QPushButton[primary="true"]:disabled {{ background: {t.rule}; border-color: {t.rule}; color: {t.muted}; }}
QToolButton[role="menu-button"] {{ padding: 4px 22px 4px 10px; }}

/* lists and tables */
QHeaderView::section {{
    background: {t.panel}; color: {t.muted}; font-weight: 600; border: none;
    border-bottom: 1px solid {t.rule}; padding: 5px 8px; }}
QTableView, QTreeView, QListView {{ border: 1px solid {t.rule}; border-radius: 4px; gridline-color: {t.rule}; }}
QSplitter::handle {{ background: transparent; }}
"""


class Theme(QObject):
    """Applies the tokens to the application and follows the system's light/dark setting."""

    changed = Signal()

    def __init__(self, app: QApplication, mode: str = "system") -> None:
        super().__init__(app)
        self.app = app
        self.mode = mode if mode in MODES else "system"
        self.tokens = LIGHT
        app.setStyle("Fusion")
        app.styleHints().colorSchemeChanged.connect(lambda _scheme: self.mode == "system" and self.apply())
        self.apply()
        global _current
        _current = self

    @property
    def is_dark(self) -> bool:
        if self.mode != "system":
            return self.mode == "dark"
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in MODES else "system"
        self.apply()

    def apply(self) -> None:
        self.tokens = DARK if self.is_dark else LIGHT
        self.app.setPalette(palette(self.tokens))
        self.app.setStyleSheet(stylesheet(self.tokens))
        self.changed.emit()


_current: Theme | None = None


def current() -> Theme | None:
    return _current


def tokens() -> Tokens:
    """The active tokens (light when no Theme is installed, e.g. in some tests)."""
    return _current.tokens if _current else LIGHT


def state_color(state: DeviceState) -> str:
    return tone_color(tokens(), STATE_TONES[state])


def on_change(slot) -> None:
    """Call slot() now and whenever the theme changes (for colours painted in code)."""
    slot()
    if _current is not None:
        _current.changed.connect(slot)


# ── charts (pyqtgraph) ──

def style_plot(plot) -> None:
    """Colour a pyqtgraph PlotWidget from the tokens; call again when the theme changes."""
    import pyqtgraph as pg

    t = tokens()
    plot.setBackground(t.field)
    for name in ("left", "bottom"):
        axis = plot.getAxis(name)
        axis.setPen(pg.mkPen(t.rule))
        axis.setTextPen(pg.mkPen(t.muted))


def series_pen(series: str = "a", width: float = 2.0):
    import pyqtgraph as pg

    return pg.mkPen(tokens().series[series], width=width)


def contrast(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two colours."""

    def luminance(color: str) -> float:
        c = QColor(color)
        channels = []
        for v in (c.redF(), c.greenF(), c.blueF()):
            channels.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        r, g, b = channels
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)
