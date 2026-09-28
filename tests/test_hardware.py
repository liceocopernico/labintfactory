"""Tests against a real photometer. Skipped unless LABDAEMON_TEST_PORT names its serial port:

    LABDAEMON_TEST_PORT=/dev/ttyACM0 uv run pytest tests/test_hardware.py
"""

import os

import pytest

from labdaemon.core.conformance import check_board
from labdaemon.core.registry import Registry
from labdaemon.transports.serial import SerialTransport
from labdaemon.transports.wire import WireClient

PORT = os.environ.get("LABDAEMON_TEST_PORT")
pytestmark = [pytest.mark.hardware, pytest.mark.skipif(not PORT, reason="set LABDAEMON_TEST_PORT")]


def test_conformance_on_real_board():
    t = SerialTransport(PORT)
    t.open()
    try:
        wire = WireClient(t)
        assert wire.wait_ready(3.5)
        info, checks = check_board(wire, Registry().load())
        assert not [c for c in checks if not c.ok]
        assert "photometer" in info.functions
    finally:
        t.close()


def test_read_light_through_the_manager(manager):
    board = manager.connect_serial(PORT)
    photo = manager.proxy(board.devices["photometer"].key)
    previous = photo.params.values()["led_power"]
    try:
        photo.set_parameter("led_power", 0)
        dark = photo.read_light(3)
        photo.set_parameter("led_power", 1500)
        lit = photo.read_light(3)
        assert lit.broadband > dark.broadband  # the LED reaches the sensor
        assert not lit.saturated
    finally:
        photo.set_parameter("led_power", previous)
