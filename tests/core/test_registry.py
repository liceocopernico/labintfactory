import textwrap

from labdaemon.core.registry import Registry, Status

GOOD_DEVICE = '''
from labdaemon.core.capabilities import TemperatureSensor
from labdaemon.core.device import Device
from labdaemon.core.i18n import N_

from .helpers import CELSIUS


class Thermometer(Device):
    id = "{id}"
    name = N_("Test thermometer")
    models = frozenset({{"thermometer"}})
    capabilities = frozenset({{TemperatureSensor}})

    def read_temperature(self):
        return 21.0
'''


def make_plugin(root, folder, *, plugin_id="thermo", api=1, device_id="test_thermometer", body=None,
                needs=()):
    d = root / folder
    d.mkdir(parents=True)
    (d / "plugin.toml").write_text(textwrap.dedent(f"""
        [plugin]
        id = "{plugin_id}"
        name = "Thermometer"
        version = "0.1.0"
        api = {api}
        needs = {list(needs)!r}

        [devices]
        {device_id} = "device:Thermometer"
    """), encoding="utf-8")
    (d / "device.py").write_text(body if body is not None else GOOD_DEVICE.format(id=device_id), encoding="utf-8")
    (d / "helpers.py").write_text('CELSIUS = "°C"\n', encoding="utf-8")  # non-ASCII on purpose (Windows)
    return d


def records_by_id(registry):
    return {r.id: r for r in registry.records()}


def test_built_in_plugins_load():
    reg = Registry().load()
    assert reg.device("tsl2591_photometer") is not None
    assert "simulated" in reg.transports()
    assert reg.device_for_model("photometer").id == "tsl2591_photometer"


def test_folder_plugin_with_relative_import(tmp_path):
    make_plugin(tmp_path, "thermo")
    reg = Registry([tmp_path]).load()
    rec = records_by_id(reg)["test_thermometer"]
    assert rec.status == Status.LOADED, rec.error
    assert rec.source == "folder"
    assert reg.device_for_model("thermometer") is rec.obj


def test_broken_and_incompatible_plugins_are_reported_not_fatal(tmp_path):
    make_plugin(tmp_path, "broken", plugin_id="broken", device_id="broken_dev", body="import nonexistent_xyz\n")
    make_plugin(tmp_path, "old", plugin_id="old", device_id="old_dev", api=0)
    make_plugin(tmp_path, "needy", plugin_id="needy", device_id="needy_dev", needs=["seabreeze_not_here"])
    make_plugin(tmp_path, "lying", plugin_id="lying", device_id="lying_dev",
                body=GOOD_DEVICE.format(id="lying_dev").replace("def read_temperature", "def other"))
    reg = Registry([tmp_path]).load()
    recs = records_by_id(reg)
    assert recs["broken_dev"].status == Status.ERROR and "nonexistent_xyz" in recs["broken_dev"].error
    assert recs["old_dev"].status == Status.INCOMPATIBLE
    assert "seabreeze_not_here" in recs["needy_dev"].error
    assert "does not implement: TemperatureSensor" in recs["lying_dev"].error
    assert reg.device("tsl2591_photometer") is not None  # built-ins unaffected


def test_override_needs_developer_mode(tmp_path):
    body = GOOD_DEVICE.format(id="tsl2591_photometer")
    make_plugin(tmp_path, "dev", plugin_id="devcopy", device_id="tsl2591_photometer", body=body)
    plain = Registry([tmp_path]).load()
    statuses = [r.status for r in plain.records() if r.id == "tsl2591_photometer"]
    assert statuses == [Status.LOADED, Status.CONFLICT]
    assert plain.device("tsl2591_photometer").__module__.startswith("labdaemon.devices")

    dev = Registry([tmp_path], developer_mode=True).load()
    statuses = [r.status for r in dev.records() if r.id == "tsl2591_photometer"]
    assert statuses == [Status.OVERRIDDEN, Status.LOADED]
    assert dev.device("tsl2591_photometer").__module__.startswith("labdaemon_ext.devcopy")
