import time

import pytest

from labdaemon.core.capabilities import LightSensor
from labdaemon.core.errors import NotReady
from labdaemon.core.experiment import Experiment, ExperimentRunner, Requirement, action, run
from labdaemon.core.wizard import ActionStep, DevicesStep
from labdaemon.devices.tsl2591 import Tsl2591Photometer
from labdaemon.devices.tsl2591 import lux as tsl


def test_photometer_hardware_sheet():
    sheet = Tsl2591Photometer.hardware_sheet()
    assert sheet.component("tsl2591").part == "TSL2591"
    assert tsl.full_scale_counts(100) == 36863 and tsl.full_scale_counts(300) == 65535
    assert sheet.spec("led", "max_power")["red"] == 4000
    assert "CH1" in sheet.notes("en") and "infrarosso" in sheet.notes("it")


class Counter(Experiment):
    id = "counter"
    name = "Counter"
    requires = {"sensor": Requirement(LightSensor, "Light sensor")}

    def setup(self):
        self.count = 0

    @action("Add one")
    def add(self, n: int = 1):
        self.count += n
        return self.count

    @run("Count")
    def count_up(self, ctx, interval: float = 0.02):
        while not ctx.cancelled:
            self.count += 1
            ctx.sleep_until_next(interval)
        return self.count

    def wizard(self):
        return [DevicesStep("Devices"), ActionStep("Add", action="add")]


def test_operations_and_steps():
    ops = Counter.operations()
    assert [(o.name, o.kind) for o in ops] == [("add", "action"), ("count_up", "run")]
    assert [p.name for p in ops[0].parameters] == ["n"] and [p.name for p in ops[1].parameters] == ["interval"]
    exp = Counter()
    devices_step, add_step = exp.wizard()
    assert not exp.step_complete(devices_step)
    with pytest.raises(NotReady):
        exp.device("sensor")
    exp.assign("sensor", object())
    assert exp.step_complete(devices_step) and not exp.step_complete(add_step)
    exp.run_operation("add", 2)
    assert exp.step_complete(add_step) and exp.session.results["_done_actions"] == ["add"]


def test_runner_runs_actions_and_stops_runs():
    exp = Counter()
    runner = ExperimentRunner(exp)
    busy = []
    runner.busy.connect(busy.append)
    assert runner.action("add", 5).result(1) == 5
    handle = runner.start("count_up", interval=0.01)
    time.sleep(0.1)
    handle.stop()
    assert handle.wait(1) > 5
    assert busy[0] is True and busy[-1] is False
    runner.shutdown()
