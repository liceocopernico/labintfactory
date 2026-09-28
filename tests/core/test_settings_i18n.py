import pytest

from labdaemon.core import i18n
from labdaemon.core.errors import ParameterError, PolicyLocked
from labdaemon.core.parameters import Parameter
from labdaemon.core.settings import Paths, Settings, plugin_dirs


def test_defaults_user_and_policy(tmp_path):
    paths = Paths.under(tmp_path)
    s = Settings(paths)
    assert s.get("app.language") == "en"
    s.set("app.language", "it")
    s.set("devices.poll_interval_s", 1.0)
    s.save()
    assert "[app]" in paths.user_settings.read_text(encoding="utf-8")
    paths.machine_dir.mkdir(parents=True)
    paths.policy.write_text('[app]\nlanguage = "en"\n[plugins]\nallow_user_plugins = false\n', encoding="utf-8")
    s2 = Settings(paths)
    assert s2.get("app.language") == "en"  # the policy wins
    assert s2.get("devices.poll_interval_s") == 1.0
    assert s2.is_locked("app.language")
    with pytest.raises(PolicyLocked):
        s2.set("app.language", "it")
    assert paths.user_plugins not in plugin_dirs(s2)  # user plugins disabled by policy


def test_plugin_dir_order(tmp_path, monkeypatch):
    s = Settings(Paths.under(tmp_path))
    monkeypatch.setenv("LABDAEMON_PLUGIN_PATH", str(tmp_path / "env"))
    dirs = plugin_dirs(s, [tmp_path / "cli"])
    assert dirs[:2] == [tmp_path / "cli", tmp_path / "env"]
    assert dirs[-2:] == [s.paths.user_plugins, s.paths.machine_plugins]


def test_italian_catalog():
    i18n.set_language("it")
    assert i18n._("Ready") == "Pronto"
    with pytest.raises(ParameterError, match="scegli tra"):
        Parameter("c", "LED colour", str, "red", choices=("red",)).validate("x")
    i18n.set_language("xx")  # unknown language falls back to English
    assert i18n.language() == "en" and i18n._("Ready") == "Ready"
