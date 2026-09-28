"""`Lab`: the same boards, devices and plugins as the desktop app, for scripts and notebooks.

    from labdaemon import Lab
    lab = Lab()
    photo = lab.simulate("tsl2591_photometer")["photometer"]
    photo.read_light(samples=3)
"""

from pathlib import Path

from labdaemon.core.manager import Board, DeviceManager
from labdaemon.core.registry import Registry
from labdaemon.core.settings import Settings, plugin_dirs
from labdaemon.core.worker import DeviceProxy


class LabBoard:
    def __init__(self, manager: DeviceManager, board: Board) -> None:
        self._manager = manager
        self._board = board

    @property
    def info(self):
        return self._board.info

    @property
    def functions(self) -> list[str]:
        return list(self._board.devices)

    def __getitem__(self, function: str) -> DeviceProxy:
        dev = self._board.devices[function]
        return self._manager.proxy(dev.key)

    def __repr__(self) -> str:
        return f"<board {self._board.name}: {', '.join(self.functions)}>"


class Lab:
    def __init__(self, *, settings: Settings | None = None, plugin_dirs_extra: list[Path] = ()) -> None:
        self.settings = settings or Settings()
        self.registry = Registry(plugin_dirs(self.settings, list(plugin_dirs_extra)),
                                 developer_mode=bool(self.settings.get("plugins.developer_mode"))).load()
        self.manager = DeviceManager(self.registry, self.settings)

    def simulate(self, plugin_id: str) -> LabBoard:
        return LabBoard(self.manager, self.manager.simulate(plugin_id))

    def scan(self):
        """What is on each USB serial port (LabInt boards, other devices, boards already connected)."""
        return self.manager.scan_serial()

    def connect(self, port: str) -> LabBoard:
        """Connect the board on a USB serial port, e.g. lab.connect("COM3") or lab.connect("/dev/ttyACM0")."""
        return LabBoard(self.manager, self.manager.connect_serial(port))

    def boards(self) -> list[LabBoard]:
        return [LabBoard(self.manager, b) for b in self.manager.boards()]

    def close(self) -> None:
        self.manager.shutdown()

    def __enter__(self) -> Lab:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
