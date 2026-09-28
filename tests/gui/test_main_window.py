import pytest

from labdaemon.core import i18n
from labdaemon.gui.app import install_translations
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.main_window import MainWindow
from labdaemon.gui.views.settings import SettingsView
from labdaemon.gui.widgets.components import PageHeader


@pytest.fixture
def window(qtbot, manager, registry, settings):
    bridge = QtBridge(manager)
    w = MainWindow(manager, registry, settings, bridge)
    qtbot.addWidget(w)
    w.show()
    return w


def test_simulated_photometer_live_reading(qtbot, window, manager):
    """The M0 exit criterion: a simulated photometer connects over the simulated wire protocol and its
    live reading updates in the status bar and the Devices view."""
    window.devices.add_simulated("tsl2591_photometer")
    qtbot.waitUntil(lambda: bool(window._chips) and "ready" in next(iter(window._chips.values())).text.text(),
                    timeout=5000)
    detail = window.devices.detail
    qtbot.waitUntil(lambda: detail.big.text().endswith("lx"), timeout=5000)
    first = detail.big.text()
    qtbot.waitUntil(lambda: detail.curve.getData()[0] is not None and len(detail.curve.getData()[0]) >= 3,
                    timeout=5000)
    assert first != "—"


def test_editing_a_setting_reaches_the_device(qtbot, window, manager):
    window.devices.add_simulated("tsl2591_photometer")
    qtbot.waitUntil(lambda: window.devices.current_key() is not None, timeout=5000)
    key = window.devices.current_key()
    window.devices.detail.form.edited.emit("led_power", 1850)
    qtbot.waitUntil(lambda: manager.snapshot(key).values["led_power"] == 1850, timeout=3000)
    window.devices.detail.form.edited.emit("led_color", "green")
    qtbot.waitUntil(lambda: manager.snapshot(key).values["led_color"] == "green", timeout=3000)
    assert manager.snapshot(key).values["led_power"] == 900  # followed the new colour's range
    window.devices.detail.form.edited.emit("led_power", 5000)  # rejected: the error is shown
    qtbot.waitUntil(lambda: "outside" in window.devices.detail.message.text(), timeout=3000)


def test_italian_interface(qtbot, qapp, settings):
    translators = install_translations(qapp, "it")
    try:
        assert translators, "labdaemon_it.qm not found"
        view = SettingsView(settings)
        qtbot.addWidget(view)
        assert view.findChild(PageHeader).title.text() == "Impostazioni"
    finally:
        for t in translators:
            qapp.removeTranslator(t)
        i18n.set_language("en")
