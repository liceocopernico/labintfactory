"""The device manager: connects boards, creates one device per board function, polls live values."""

import itertools
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from labdaemon.core.board import BoardAddress, BoardInfo
from labdaemon.core.data import Channel
from labdaemon.core.device import Command, Device, DeviceState
from labdaemon.core.errors import LabError, PluginError, ProtocolTimeout, TransportError
from labdaemon.core.events import Signal
from labdaemon.core.i18n import _
from labdaemon.core.parameters import Parameter
from labdaemon.core.registry import Registry
from labdaemon.core.settings import Settings
from labdaemon.core.transport import Transport
from labdaemon.core.worker import BoardWorker, DeviceProxy
from labdaemon.transports.serial import PortInfo, SerialTransport, list_ports
from labdaemon.transports.simulated import SimulatedTransport
from labdaemon.transports.wire import WireClient

_sim_numbers = itertools.count(1)


@dataclass
class Board:
    address: BoardAddress
    transport: Transport
    wire: WireClient
    worker: BoardWorker
    info: BoardInfo | None = None
    devices: dict[str, Device] = field(default_factory=dict)  # function name → device
    unsupported: list[str] = field(default_factory=list)  # functions no installed plugin serves

    @property
    def key(self) -> str:
        return self.info.serial if self.info else str(self.address)

    @property
    def name(self) -> str:
        return self.info.name if self.info else str(self.address)


@dataclass(frozen=True)
class ScanResult:
    """What a USB port holds: a LabInt board (with its functions), something else, or a connected board."""

    port: PortInfo
    info: BoardInfo | None = None
    plugins: dict[str, str | None] = field(default_factory=dict)  # function → plugin id (None: no plugin)
    connected: bool = False
    error: str | None = None


@dataclass(frozen=True)
class DeviceSnapshot:
    """A consistent, thread-safe view of a device for the GUI."""

    key: str
    plugin_id: str
    plugin_name: str
    function: str
    board: BoardInfo
    address: BoardAddress
    state: DeviceState
    parameters: list[Parameter]
    values: dict[str, Any]
    commands: list[Command]
    channels: list[Channel]


class DeviceManager:
    def __init__(self, registry: Registry, settings: Settings | None = None) -> None:
        self.registry = registry
        self.settings = settings
        self._boards: dict[str, Board] = {}
        self._states: dict[str, DeviceState] = {}
        self._lock = threading.RLock()
        self.boards_changed = Signal("manager.boards_changed")  # ()
        self.device_state = Signal("manager.device_state")  # (device key, DeviceState)
        self.sample = Signal("manager.sample")  # (device key, {channel: value}, monotonic time)
        self.parameters_changed = Signal("manager.parameters_changed")  # (device key)
        self.error = Signal("manager.error")  # (device or board key, LabError)
        self.board_event = Signal("manager.board_event")  # (board key, Event)

    # ── connecting ──
    def simulate(self, plugin_id: str, *, name: str | None = None) -> Board:
        """Connect the simulated twin that a device plugin ships."""
        cls = self.registry.device(plugin_id)
        if cls is None or cls.simulated is None:
            raise PluginError(_("No simulated device is available for {plugin}.").format(plugin=plugin_id))
        sim = cls.simulated()
        n = next(_sim_numbers)
        sim.name = name or f"Sim-{n}"
        sim.serial = f"SIM{n:04d}"
        return self.connect(SimulatedTransport(sim), BoardAddress("simulated", plugin_id))

    def connect_serial(self, port: str) -> Board:
        return self.connect(SerialTransport(port), BoardAddress("serial", port))

    def scan_serial(self, *, timeout: float = 3.5) -> list[ScanResult]:
        """Ask every USB serial port that is not connected yet who it is (in parallel)."""
        connected = {b.address.target: b for b in self.boards() if b.address.link == "serial"}
        ports = list_ports()

        def probe(port: PortInfo) -> ScanResult:
            if port.device in connected:
                board = connected[port.device]
                return ScanResult(port, board.info, self._plugins_for(board.info), connected=True)
            transport = SerialTransport(port.device)
            wire = WireClient(transport)
            try:
                transport.open()
                if not wire.wait_ready(timeout):
                    return ScanResult(port, error=_("no answer to PING"))
                info = wire.identify()
                return ScanResult(port, info, self._plugins_for(info))
            except LabError as e:
                return ScanResult(port, error=e.message)
            finally:
                transport.close()

        if not ports:
            return []
        with ThreadPoolExecutor(max_workers=min(8, len(ports)), thread_name_prefix="scan") as pool:
            return list(pool.map(probe, ports))

    def _plugins_for(self, info: BoardInfo | None) -> dict[str, str | None]:
        if info is None:
            return {}
        return {fn: (cls.id if (cls := self.registry.device_for_model(fn)) else None) for fn in info.functions}

    def connect(self, transport: Transport, address: BoardAddress, *, timeout: float = 8.0) -> Board:
        wire = WireClient(transport)
        worker = BoardWorker(str(address), idle=wire.pump)
        board = Board(address, transport, wire, worker)
        worker.start()
        try:
            worker.call(self._open_board, board, timeout=timeout)
        except BaseException:
            try:
                worker.call(self._close_board, board, timeout=2.0)
            except Exception as e:
                logger.debug("cleanup after failed connect: {}", e)
            worker.shutdown()
            raise
        with self._lock:
            if board.key in self._boards:
                worker.call(self._close_board, board)
                worker.shutdown()
                raise LabError(_("{board} is already connected.").format(board=board.name))
            self._boards[board.key] = board
        interval = float(self.settings.get("devices.poll_interval_s", 0.5)) if self.settings else 0.5
        worker.polled.connect(self._on_polled)
        worker.poll_failed.connect(lambda key, exc, b=board: self._on_poll_failed(b, key, exc))
        for dev in board.devices.values():
            self._set_state(dev.key, DeviceState.READY)
            if type(dev).poll is not Device.poll:
                worker.add_poll(dev.key, dev.poll, interval)
        logger.info("connected {} ({}), functions {}", board.name, address, list(board.info.functions))
        self.boards_changed.emit()
        return board

    def disconnect(self, board_key: str) -> None:
        with self._lock:
            board = self._boards.pop(board_key, None)
        if board is None:
            return
        try:
            board.worker.call(self._close_board, board, timeout=3.0)
        except Exception as e:
            logger.warning("closing {}: {}", board.name, e)
        board.worker.shutdown()
        for dev in board.devices.values():
            self._set_state(dev.key, DeviceState.DISCONNECTED)
            self._states.pop(dev.key, None)
        self.boards_changed.emit()

    def shutdown(self) -> None:
        for key in list(self._boards):
            self.disconnect(key)

    # worker-thread side
    def _open_board(self, board: Board) -> None:
        board.transport.open()
        if not board.wire.wait_ready(3.5):
            raise ProtocolTimeout(_("{target} does not answer. Is it a LabDaemon board with LabInt firmware?")
                                  .format(target=board.address.target))
        board.info = board.wire.identify()
        for fn in board.info.functions:
            cls = self.registry.device_for_model(fn)
            if cls is None:
                board.unsupported.append(fn)
                continue
            dev = cls(board.wire.function(fn), board.info)
            dev.open()
            dev.params.changed.connect(lambda _values, _defs, key=dev.key: self.parameters_changed.emit(key))
            board.devices[fn] = dev
        board.wire.debug.connect(lambda text, b=board: logger.debug("{} # {}", b.name, text))
        board.wire.events.connect(lambda ev, b=board: self.board_event.emit(b.key, ev))

    def _close_board(self, board: Board) -> None:
        for dev in board.devices.values():
            try:
                dev.close()
            except Exception as e:
                logger.warning("closing {}: {}", dev.key, e)
        board.wire.fail_pending(TransportError(_("The board was disconnected.")))
        if board.transport.is_open:
            board.transport.close()

    def _on_polled(self, key: str, values: Any, t: float) -> None:
        if values is None:
            return
        if self._states.get(key) in (DeviceState.ERROR, DeviceState.LOST):
            self._set_state(key, DeviceState.READY)
        self.sample.emit(key, values, t)

    def _on_poll_failed(self, board: Board, key: str, exc: Exception) -> None:
        if isinstance(exc, TransportError):
            for dev in board.devices.values():
                self._set_state(dev.key, DeviceState.LOST)
        else:
            self._set_state(key, DeviceState.ERROR)
        self.error.emit(key, exc if isinstance(exc, LabError) else LabError(str(exc)))

    def _set_state(self, key: str, state: DeviceState) -> None:
        if self._states.get(key) != state:
            self._states[key] = state
            self.device_state.emit(key, state)

    # ── queries (any thread) ──
    def boards(self) -> list[Board]:
        with self._lock:
            return list(self._boards.values())

    def board(self, board_key: str) -> Board:
        with self._lock:
            return self._boards[board_key]

    def device_keys(self) -> list[str]:
        return [d.key for b in self.boards() for d in b.devices.values()]

    def devices_providing(self, capability: type) -> list[str]:
        """Connected devices whose plugin provides a capability (candidates for an experiment role)."""
        return [d.key for b in self.boards() for d in b.devices.values() if d.provides(capability)]

    def state(self, key: str) -> DeviceState:
        return self._states.get(key, DeviceState.DISCONNECTED)

    def snapshot(self, key: str) -> DeviceSnapshot:
        board, dev = self._find(key)
        return DeviceSnapshot(
            key=key, plugin_id=dev.id, plugin_name=dev.name, function=dev.function, board=dev.board,
            address=board.address, state=self.state(key), parameters=dev.params.definitions(),
            values=dev.params.values(), commands=dev.commands(), channels=dev.channels())

    # ── acting on devices ──
    def submit(self, key: str, method: str, /, *args: Any, **kwargs: Any) -> Future:
        """From the GUI: run device.method(*args) on its board's worker; returns a Future at once."""
        board, dev = self._find(key)
        return board.worker.submit(getattr(dev, method), *args, **kwargs)

    def proxy(self, key: str) -> DeviceProxy:
        board, dev = self._find(key)
        return DeviceProxy(board.worker, dev)

    def run_on_board(self, board_key: str, fn: Callable[[WireClient], Any]) -> Future:
        board = self.board(board_key)
        return board.worker.submit(fn, board.wire)

    def _find(self, key: str) -> tuple[Board, Device]:
        board_key, _sep, fn = key.partition("/")
        with self._lock:
            board = self._boards.get(board_key)
        if board is None or fn not in board.devices:
            raise LabError(_("That device is not connected."), detail=key)
        return board, board.devices[fn]
