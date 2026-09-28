import pytest

from labdaemon.core.session import Session
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.experiment.guided import ActionPage, ParametersPage, TablePage
from labdaemon.gui.main_window import MainWindow


@pytest.fixture
def window(qtbot, manager, registry, settings):
    w = MainWindow(manager, registry, settings, QtBridge(manager))
    qtbot.addWidget(w)
    w.show()
    return w


def cuvette(manager, board, a):
    manager.run_on_board(board.key, lambda wire: wire.query("SIM", f"absorbance={a}", fn="photometer")).result(1)


def test_guided_absorbance_lab(qtbot, window, manager, tmp_path):
    board = manager.simulate("tsl2591_photometer")
    host = window.experiments.open_experiment(manager.registry.experiment("absorbance"))
    guided = host.guided
    qtbot.waitUntil(lambda: not host.experiment.missing_roles(), timeout=3000)  # the only photometer: auto-assigned
    guided.go(1)
    page = guided.page_list[1]
    assert isinstance(page, ParametersPage)
    page.device_form.edited.emit("led_power", 1850)
    qtbot.waitUntil(lambda: guided.next.isEnabled(), timeout=5000)  # live reading good → Next
    guided.go(2)
    guided.go(3)
    action = guided.page_list[3]
    assert isinstance(action, ActionPage)
    cuvette(manager, board, 0.0)
    action.button.click()
    qtbot.waitUntil(lambda: "I₀" in action.result.text(), timeout=5000)
    guided.go(4)
    table = guided.page_list[4]
    assert isinstance(table, TablePage)
    for c in ("0.02", "0,04", "0.06"):  # both decimal separators are accepted
        cuvette(manager, board, 6.785 * float(c.replace(",", ".")))
        table.input.setText(c)
        table.button.click()
        qtbot.waitUntil(lambda: table.button.isEnabled() and not table.input.text(), timeout=5000)
    qtbot.waitUntil(lambda: "R²" in table.summary.text(), timeout=3000)
    assert host.experiment.count_standards() == 3 and guided.next.isEnabled()
    guided.go(5)
    unknown = guided.page_list[5]
    cuvette(manager, board, 0.3)
    unknown.input.setText("sample X")
    unknown.button.click()
    qtbot.waitUntil(lambda: "sample X" in unknown.summary.text(), timeout=5000)
    guided.go(6)
    assert guided.page_list[6].form.rowCount() >= 5
    path = host.save_session(tmp_path / "lab.labint")
    assert Session.load(path).results["formula"].startswith("A = ")
    assert window.settings_view.settings.get("experiments.absorbance.mode") == "expert"


def test_expert_view_and_reopening(qtbot, window, manager, tmp_path):
    board = manager.simulate("tsl2591_photometer")
    manager.proxy(board.devices["photometer"].key).set_parameter("led_power", 1850)
    host = window.experiments.open_experiment(manager.registry.experiment("absorbance"))
    host.set_mode("expert")
    expert = host.expert
    ops = {b.text(): b for b in expert.buttons}
    ops["Measure blank"].click()
    qtbot.waitUntil(lambda: expert.tables["standards"].rowCount() == 1, timeout=5000)
    for c in ("0.02", "0.05"):
        cuvette(manager, board, 6.785 * float(c))
        expert._inputs["measure_standard"]["concentration"].setText(c)
        ops["Measure standard"].click()
        qtbot.waitUntil(lambda: expert.tables["standards"].rowCount() >= 2 and ops["Measure standard"].isEnabled(),
                        timeout=5000)
    qtbot.waitUntil(lambda: "R²" in expert.summary.text(), timeout=3000)
    path = host.save_session(tmp_path / "expert.labint")
    assert host.close_experiment()
    reopened = window.experiments.open_session(path)
    assert reopened.experiment.count_standards() == 2 and reopened.experiment.fit is not None
    assert not reopened.dirty
