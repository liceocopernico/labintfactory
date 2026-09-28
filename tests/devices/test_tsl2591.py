import pytest

from labdaemon.core.capabilities import LightSensor, LightSource, Sensor
from labdaemon.core.errors import ParameterError
from labdaemon.devices.tsl2591 import Tsl2591Photometer
from labdaemon.devices.tsl2591 import lux as tsl


def test_lux_formula_matches_the_design_example():
    assert tsl.lux(5691, 1899, 100, 25) == pytest.approx(412.35, abs=0.01)
    assert tsl.lux(0, 0, 100, 25) == 0.0
    assert tsl.full_scale_counts(100) == 36863 and tsl.full_scale_counts(200) == 65535


def test_plugin_implements_its_capabilities():
    for cap in (LightSensor, LightSource, Sensor):
        assert Tsl2591Photometer.provides(cap)


@pytest.fixture
def photometer(manager):
    board = manager.simulate("tsl2591_photometer")
    dev = board.devices["photometer"]
    return board, manager.proxy(dev.key)


def test_blank_reads_about_412_lux(photometer):
    _board, photo = photometer
    r = photo.read_light(5)
    assert r.lux == pytest.approx(412.4, rel=0.01)
    assert not r.saturated


def test_absorbance_of_the_sample(manager, photometer):
    board, photo = photometer
    manager.run_on_board(board.key, lambda wire: wire.query("SIM", "absorbance=0.5", fn="photometer")).result(1)
    assert photo.read_light(5).lux == pytest.approx(412.4 * 10 ** -0.5, rel=0.02)


def test_colour_change_brings_power_into_range(photometer):
    _board, photo = photometer
    values = photo.set_parameter("led_color", "orange")
    assert values["led_power"] == 850
    with pytest.raises(ParameterError):
        photo.set_parameter("led_power", 1000)  # outside 780–850: user input is rejected, not clamped
    with pytest.raises(ParameterError):
        photo.set_parameter("led_color", "purple")


def test_high_gain_saturates(photometer):
    _board, photo = photometer
    photo.set_parameter("gain", 428)
    assert photo.read_light().saturated


def test_settings_are_read_back_from_the_board(manager, photometer):
    board, photo = photometer
    manager.run_on_board(board.key, lambda wire: wire.query("CFG", 300, 1, fn="photometer")).result(1)
    photo.run_command("refresh")
    assert photo.params.values()["integration_time"] == 300
