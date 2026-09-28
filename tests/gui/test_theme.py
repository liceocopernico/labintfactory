import re
from dataclasses import fields
from pathlib import Path

import pytest

import labdaemon.gui as gui_pkg
from labdaemon.core.device import DeviceState
from labdaemon.gui import theme
from labdaemon.gui.widgets.components import StatePill


@pytest.mark.parametrize("t", [theme.LIGHT, theme.DARK], ids=lambda t: t.name)
def test_tokens_are_readable(t):
    """WCAG AA: 4.5:1 for normal text; body text aims higher."""
    assert theme.contrast(t.ink, t.win) >= 7
    for fg in (t.muted, t.ok, t.warn, t.err, t.sel_text):
        for bg in (t.win, t.panel):
            assert theme.contrast(fg, bg) >= 4.5, (fg, bg)
    assert theme.contrast(t.sel_ink, t.sel) >= 4.5
    assert theme.contrast(t.sel_text, t.sel_soft) >= 4.5  # selected rail item


def test_both_variants_define_the_same_tokens():
    for f in fields(theme.Tokens):
        assert getattr(theme.LIGHT, f.name) and getattr(theme.DARK, f.name)
    assert theme.LIGHT.series.keys() == theme.DARK.series.keys()


FORBIDDEN = [
    (re.compile(r"setStyleSheet\("), "writes its own stylesheet"),
    (re.compile(r"#[0-9A-Fa-f]{6}\b"), "hard-codes a colour"),
    (re.compile(r"Qt\.GlobalColor\.(?!transparent)"), "uses a fixed Qt colour"),
    (re.compile(r"mkPen\(\s*['\"]"), "hard-codes a chart colour"),
]


def test_views_do_not_paint_themselves():
    """Colours and stylesheets live in gui/theme.py only (design: theme foundation)."""
    root = Path(gui_pkg.__file__).parent
    problems = []
    for path in root.rglob("*.py"):
        if path.name == "theme.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, why in FORBIDDEN:
                if pattern.search(line):
                    problems.append(f"{path.relative_to(root)}:{n} {why}: {line.strip()}")
    assert not problems, "\n".join(problems)


def test_theme_switches_palette_and_components(qapp, qtbot):
    t = theme.Theme(qapp, "dark")
    try:
        assert qapp.palette().window().color().name() == theme.DARK.win.lower()
        assert theme.tokens() is theme.DARK
        pill = StatePill()
        qtbot.addWidget(pill)
        pill.set_state(DeviceState.READY)
        assert pill.property("pill") == "ok" and pill.text() == "Ready"
        seen = []
        t.changed.connect(lambda: seen.append(theme.tokens().name))
        t.set_mode("light")
        assert seen == ["light"]
        assert qapp.palette().window().color().name() == theme.LIGHT.win.lower()
    finally:
        t.set_mode("light")
