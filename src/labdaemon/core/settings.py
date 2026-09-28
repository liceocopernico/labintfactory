"""User settings and the machine policy.

Values resolve in this order: machine policy (admin-writable, cannot be changed from the app),
then user settings, then defaults. Keys are dotted: "app.language", "student.mode" …
"""

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import platformdirs
import tomli_w
from loguru import logger

from labdaemon.core.errors import PolicyLocked
from labdaemon.core.i18n import _

APP = "labdaemon"

DEFAULTS: dict[str, Any] = {
    "app.language": "en",
    "app.theme": "system",  # system | light | dark
    "devices.poll_interval_s": 0.5,
    "plugins.allow_user_plugins": True,
    "plugins.developer_mode": False,
    "plugins.extra_dirs": [],
    "student.mode": "off",  # forced | default | off (the lock itself arrives in M2)
}


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    data_dir: Path
    log_dir: Path
    user_plugins: Path
    machine_dir: Path  # policy.toml and machine-wide plugins

    @property
    def user_settings(self) -> Path:
        return self.config_dir / "settings.toml"

    @property
    def policy(self) -> Path:
        return self.machine_dir / "policy.toml"

    @property
    def machine_plugins(self) -> Path:
        return self.machine_dir / "plugins"

    @classmethod
    def default(cls) -> Paths:
        if sys.platform == "win32":
            machine = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "LabDaemon"
        else:
            machine = Path("/etc/labdaemon")
        data = Path(platformdirs.user_data_dir(APP, appauthor=False))
        return cls(
            config_dir=Path(platformdirs.user_config_dir(APP, appauthor=False)),
            data_dir=data,
            log_dir=Path(platformdirs.user_log_dir(APP, appauthor=False)),
            user_plugins=data / "plugins",
            machine_dir=machine,
        )

    @classmethod
    def under(cls, root: Path) -> Paths:
        """Everything below one folder: for tests and portable setups."""
        return cls(root / "config", root / "data", root / "logs", root / "data" / "plugins", root / "machine")


def flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in tree.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, full + "."))
        else:
            out[full] = value
    return out


def nest(flat: dict[str, Any]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for key, value in flat.items():
        node = tree
        *parents, leaf = key.split(".")
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = value
    return tree


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return flatten(tomllib.load(f))
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning("ignoring unreadable settings file {}: {}", path, e)
        return {}


class Settings:
    def __init__(self, paths: Paths | None = None) -> None:
        self.paths = paths or Paths.default()
        self._policy = _read_toml(self.paths.policy)
        self._user = _read_toml(self.paths.user_settings)

    def get(self, key: str, default: Any = None) -> Any:
        for layer in (self._policy, self._user, DEFAULTS):
            if key in layer:
                return layer[key]
        return default

    def is_locked(self, key: str) -> bool:
        return key in self._policy

    def set(self, key: str, value: Any) -> None:
        if self.is_locked(key):
            raise PolicyLocked(_("This setting is fixed by your administrator."))
        self._user[key] = value

    def save(self) -> None:
        path = self.paths.user_settings
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(tomli_w.dumps(nest(self._user)), encoding="utf-8")
        tmp.replace(path)


def plugin_dirs(settings: Settings, extra: list[Path] | tuple[Path, ...] = ()) -> list[Path]:
    """Plugin folders in search order: command line, LABDAEMON_PLUGIN_PATH, user folder, machine folder."""
    dirs = [Path(p) for p in extra]
    env = os.environ.get("LABDAEMON_PLUGIN_PATH")
    if env:
        dirs += [Path(p) for p in env.split(os.pathsep) if p]
    dirs += [Path(p) for p in settings.get("plugins.extra_dirs", [])]
    if settings.get("plugins.allow_user_plugins", True):
        dirs.append(settings.paths.user_plugins)
    dirs.append(settings.paths.machine_plugins)
    seen: set[Path] = set()
    return [d for d in dirs if not (d in seen or seen.add(d))]
