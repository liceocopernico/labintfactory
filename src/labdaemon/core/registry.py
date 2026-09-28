"""Plugin discovery: entry points for built-in plugins, plugin folders for development and unpackaged ones.

Both routes use the same table shape, so one loader handles them:

    [devices]                                  # plugin.toml of a folder plugin
    ccd_spectrometer = "device:CcdSpectrometer"

    [project.entry-points."labdaemon.devices"] # pyproject.toml of LabDaemon itself
    tsl2591_photometer = "labdaemon.devices.tsl2591:Tsl2591Photometer"
"""

import importlib
import importlib.metadata
import importlib.util
import sys
import tomllib
import traceback
import types
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from loguru import logger

from labdaemon.core import API_VERSION
from labdaemon.core.capabilities import ALL as KNOWN_CAPABILITIES
from labdaemon.core.device import Device
from labdaemon.core.i18n import add_catalog
from labdaemon.core.transport import Transport

GROUPS = {"transports": "labdaemon.transports", "devices": "labdaemon.devices",
          "experiments": "labdaemon.experiments"}
KINDS = {"transports": "transport", "devices": "device", "experiments": "experiment"}
EXT_NAMESPACE = "labdaemon_ext"


class Status(StrEnum):
    LOADED = "loaded"
    ERROR = "error"
    INCOMPATIBLE = "incompatible"
    OVERRIDDEN = "overridden"
    CONFLICT = "conflict"


@dataclass
class PluginRecord:
    id: str
    kind: str  # "transport" | "device" | "experiment"
    source: str  # "built-in" | "folder"
    origin: str  # distribution name, or the plugin folder
    version: str
    api: int
    status: Status
    obj: type | None = None
    error: str | None = None

    @property
    def name(self) -> str:
        return getattr(self.obj, "name", self.id) if self.obj else self.id


class Registry:
    def __init__(self, plugin_dirs: Iterable[Path] = (), *, developer_mode: bool = False) -> None:
        self.plugin_dirs = [Path(d) for d in plugin_dirs]
        self.developer_mode = developer_mode
        self._records: list[PluginRecord] = []

    # ── queries ──
    def records(self) -> list[PluginRecord]:
        return list(self._records)

    def devices(self) -> dict[str, type[Device]]:
        return {r.id: r.obj for r in self._active("device")}

    def transports(self) -> dict[str, type[Transport]]:
        return {r.id: r.obj for r in self._active("transport")}

    def device(self, plugin_id: str) -> type[Device] | None:
        return self.devices().get(plugin_id)

    def device_for_model(self, model: str) -> type[Device] | None:
        """The device plugin serving a function name from a board's ID? reply."""
        for cls in self.devices().values():
            if model in cls.models:
                return cls
        return None

    def _active(self, kind: str) -> list[PluginRecord]:
        return [r for r in self._records if r.kind == kind and r.status == Status.LOADED and r.obj]

    # ── loading ──
    def load(self) -> Registry:
        self._records.clear()
        self._load_entry_points()
        for folder in self.plugin_dirs:
            if folder.is_dir():
                for plugin_dir in sorted(p for p in folder.iterdir() if (p / "plugin.toml").is_file()):
                    self._load_folder(plugin_dir)
        for r in self._records:
            if r.status != Status.LOADED:
                logger.warning("plugin {} ({}): {}", r.id, r.status, (r.error or "").splitlines()[0:1])
        return self

    def _load_entry_points(self) -> None:
        for group_key, group in GROUPS.items():
            for ep in importlib.metadata.entry_points(group=group):
                dist = ep.dist
                self._add(ep.name, KINDS[group_key], "built-in", dist.name if dist else "?",
                          dist.version if dist else "?", API_VERSION, ep.value, ep.load)

    def _load_folder(self, plugin_dir: Path) -> None:
        try:
            manifest = tomllib.loads((plugin_dir / "plugin.toml").read_text(encoding="utf-8"))
            meta = manifest["plugin"]
            plugin_id = str(meta["id"])
            version = str(meta.get("version", "0"))
            api = int(meta.get("api", 0))
        except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as e:
            self._records.append(PluginRecord(plugin_dir.name, "device", "folder", str(plugin_dir), "?", 0,
                                              Status.ERROR, error=f"plugin.toml: {e}"))
            return
        entries = [(name, KINDS[key], target) for key in GROUPS
                   for name, target in manifest.get(key, {}).items()]
        if api != API_VERSION:
            for name, kind, _target in entries:
                self._records.append(PluginRecord(
                    name, kind, "folder", str(plugin_dir), version, api, Status.INCOMPATIBLE,
                    error=f"written for plugin API {api}; this LabDaemon has API {API_VERSION}"))
            return
        missing = [m for m in meta.get("needs", []) if importlib.util.find_spec(m) is None]
        package = f"{EXT_NAMESPACE}.{plugin_id}"
        for name, kind, target in entries:
            if missing:
                self._records.append(PluginRecord(
                    name, kind, "folder", str(plugin_dir), version, api, Status.ERROR,
                    error=f"needs packages that are not installed: {', '.join(missing)}"))
                continue
            self._add(name, kind, "folder", str(plugin_dir), version, api, target,
                      lambda t=target: _load_from_folder(plugin_dir, package, t))
        locale = plugin_dir / "locale"
        if locale.is_dir():
            add_catalog(plugin_id, locale)

    def _add(self, name, kind, source, origin, version, api, target, loader) -> None:
        record = PluginRecord(name, kind, source, origin, version, api, Status.ERROR)
        try:
            obj = loader()
            _validate(name, kind, obj)
            record.obj, record.status = obj, Status.LOADED
        except Exception:
            record.error = f"{target}\n{traceback.format_exc(limit=3)}"
        existing = next((r for r in self._records
                         if r.id == name and r.kind == kind and r.status == Status.LOADED), None)
        if existing and record.status == Status.LOADED:
            if source == "folder" and self.developer_mode:
                existing.status = Status.OVERRIDDEN
            else:
                record.status = Status.CONFLICT
                record.error = f"id {name!r} is already provided by {existing.origin}"
        self._records.append(record)


def _validate(name: str, kind: str, obj: object) -> None:
    if kind == "device":
        if not (isinstance(obj, type) and issubclass(obj, Device)):
            raise TypeError(f"{obj!r} is not a Device subclass")
        for attr in ("id", "name", "models", "capabilities"):
            if not hasattr(obj, attr):
                raise TypeError(f"{obj.__name__} lacks the class attribute {attr!r}")
        if obj.id != name:
            raise TypeError(f"{obj.__name__}.id is {obj.id!r} but it is registered as {name!r}")
        unknown = [c for c in obj.capabilities if c not in KNOWN_CAPABILITIES]
        if unknown:
            raise TypeError(f"unknown capabilities: {unknown}")
        missing = [c.__name__ for c in obj.capabilities
                   if any(not callable(getattr(obj, m, None)) for m in _protocol_methods(c))]
        if missing:
            raise TypeError(f"{obj.__name__} declares but does not implement: {', '.join(missing)}")
    elif kind == "transport":
        if not (isinstance(obj, type) and issubclass(obj, Transport)):
            raise TypeError(f"{obj!r} is not a Transport subclass")


def _protocol_methods(capability: type) -> list[str]:
    return [n for n, v in vars(capability).items() if callable(v) and not n.startswith("_")]


def _load_from_folder(plugin_dir: Path, package: str, target: str) -> object:
    """Import `module:Attr` from a plugin folder as the private package labdaemon_ext.<id>."""
    if EXT_NAMESPACE not in sys.modules:
        ns = types.ModuleType(EXT_NAMESPACE)
        ns.__path__ = []
        sys.modules[EXT_NAMESPACE] = ns
    if package not in sys.modules:
        module = types.ModuleType(package)
        module.__path__ = [str(plugin_dir)]
        module.__package__ = package
        sys.modules[package] = module
        init = plugin_dir / "__init__.py"
        if init.exists():
            spec = importlib.util.spec_from_file_location(
                package, init, submodule_search_locations=[str(plugin_dir)])
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load {init}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[package] = module
            spec.loader.exec_module(module)
    module_name, _sep, attr = target.partition(":")
    module = importlib.import_module(f"{package}.{module_name}")
    return getattr(module, attr)
