"""OSC server/client for DAW communication (python-osc)."""

from __future__ import annotations

import asyncio
from typing import Callable, Dict, List

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


OSCHandler = Callable[[str, List[float]], None]


class OSCBridge:
    """Bidirectional OSC bridge.

    Receives:
        /transport/play
        /transport/stop
        /transport/pause
        /transport/bpm  f
        /constraint/{name}/set/{param}  f
        /constraint/{name}/trigger

    Sends:
        /transport/tick  i
        /transport/beat  i
        /transport/bar   i
        /midi/note_on    iif  (note, velocity, channel)
        /midi/note_off   ii   (note, channel)
    """

    def __init__(
        self,
        listen_host: str = "127.0.0.1",
        listen_port: int = 8000,
        send_host: str = "127.0.0.1",
        send_port: int = 9000,
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.send_host = send_host
        self.send_port = send_port
        self._dispatcher = Dispatcher()
        self._server: AsyncIOOSCUDPServer | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: asyncio.DatagramProtocol | None = None
        self._client = SimpleUDPClient(send_host, send_port)
        self._handlers: Dict[str, List[OSCHandler]] = {}
        self._setup_default_routes()

    def _setup_default_routes(self) -> None:
        self._dispatcher.map("/transport/play", self._on_play)
        self._dispatcher.map("/transport/stop", self._on_stop)
        self._dispatcher.map("/transport/pause", self._on_pause)
        self._dispatcher.map("/transport/bpm", self._on_bpm)
        self._dispatcher.map("/constraint/*/set/*", self._on_constraint_set)
        self._dispatcher.map("/constraint/*/trigger", self._on_constraint_trigger)

    def register(self, address: str, handler: OSCHandler) -> None:
        self._handlers.setdefault(address, []).append(handler)

    def unregister(self, address: str, handler: OSCHandler) -> None:
        if address in self._handlers and handler in self._handlers[address]:
            self._handlers[address].remove(handler)

    def _emit(self, address: str, args: List[float]) -> None:
        for h in list(self._handlers.get(address, [])):
            try:
                h(address, args)
            except Exception:
                pass

    def _on_play(self, addr: str, *args) -> None:
        self._emit("/transport/play", [])

    def _on_stop(self, addr: str, *args) -> None:
        self._emit("/transport/stop", [])

    def _on_pause(self, addr: str, *args) -> None:
        self._emit("/transport/pause", [])

    def _on_bpm(self, addr: str, *args) -> None:
        if args:
            self._emit("/transport/bpm", [float(args[0])])

    def _on_constraint_set(self, addr: str, *args) -> None:
        parts = addr.split("/")
        if len(parts) >= 5:
            name = parts[2]
            param = parts[4]
            value = float(args[0]) if args else 0.0
            self._emit(f"/constraint/{name}/set/{param}", [value])

    def _on_constraint_trigger(self, addr: str, *args) -> None:
        parts = addr.split("/")
        if len(parts) >= 3:
            name = parts[2]
            self._emit(f"/constraint/{name}/trigger", [])

    # ---- client send helpers ----

    def send(self, address: str, *values) -> None:
        self._client.send_message(address, list(values))

    def send_tick(self, tick: int) -> None:
        self.send("/transport/tick", tick)

    def send_beat(self, beat: int) -> None:
        self.send("/transport/beat", beat)

    def send_bar(self, bar: int) -> None:
        self.send("/transport/bar", bar)

    def send_note_on(self, note: int, velocity: int, channel: int = 0) -> None:
        self.send("/midi/note_on", note, velocity, channel)

    def send_note_off(self, note: int, channel: int = 0) -> None:
        self.send("/midi/note_off", note, channel)

    def send_bpm(self, bpm: float) -> None:
        self.send("/transport/bpm", bpm)

    # ---- server lifecycle ----

    async def start(self) -> None:
        self._server = AsyncIOOSCUDPServer(
            (self.listen_host, self.listen_port),
            self._dispatcher,
            asyncio.get_event_loop(),
        )
        self._transport, self._protocol = await self._server.create_serve_endpoint()

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None

    def __repr__(self) -> str:
        return (
            f"OSCBridge(listen={self.listen_host}:{self.listen_port}, "
            f"send={self.send_host}:{self.send_port})"
        )
