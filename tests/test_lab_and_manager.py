import time

import pytest

from labdaemon import Lab
from labdaemon.core.device import DeviceState
from labdaemon.core.errors import LabError, PluginError


def test_lab_facade(settings):
    with Lab(settings=settings) as lab:
        board = lab.simulate("tsl2591_photometer")
        assert board.functions == ["photometer"]
        photo = board["photometer"]
        assert photo.read_light().lux > 400
        assert len(lab.boards()) == 1
    assert lab.boards() == []


def test_manager_polls_and_reports_state(manager):
    samples, states = [], []
    manager.sample.connect(lambda key, values, t: samples.append(values))
    manager.device_state.connect(lambda key, state: states.append(state))
    board = manager.simulate("tsl2591_photometer")
    key = board.devices["photometer"].key
    assert manager.state(key) == DeviceState.READY
    deadline = time.monotonic() + 3
    while len(samples) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert samples and samples[-1]["lux"] > 400
    snap = manager.snapshot(key)
    assert snap.values["led_color"] == "red" and snap.board.functions == ("photometer",)
    manager.disconnect(board.key)
    assert states[-1] == DeviceState.DISCONNECTED
    with pytest.raises(LabError):
        manager.snapshot(key)


def test_two_simulated_boards_are_distinct(manager):
    a = manager.simulate("tsl2591_photometer")
    b = manager.simulate("tsl2591_photometer")
    assert a.key != b.key and len(manager.boards()) == 2


def test_unknown_plugin_cannot_be_simulated(manager):
    with pytest.raises(PluginError):
        manager.simulate("nope")
