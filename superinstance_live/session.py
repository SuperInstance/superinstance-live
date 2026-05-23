"""Session class that holds state for running compositions."""

from __future__ import annotations

import asyncio
from typing import List, Optional

from .transport import Transport, TransportState
from .constraint_host import ConstraintHost, PipelineEvent
from .midi_clock import MidiClockOut
from .osc_bridge import OSCBridge


class Session:
    """Orchestrates transport, constraint host, MIDI clock, and OSC."""

    def __init__(
        self,
        bpm: float = 120.0,
        osc_listen_port: int = 8000,
        osc_send_port: int = 9000,
        midi_port: str | None = None,
    ):
        self.transport = Transport(bpm=bpm)
        self.host = ConstraintHost()
        self.midi_clock = MidiClockOut(port_name=midi_port)
        self.osc = OSCBridge(
            listen_port=osc_listen_port,
            send_port=osc_send_port,
        )
        self._wire_up()

    def _wire_up(self) -> None:
        # Transport → MIDI clock + OSC + Constraint host
        self.transport.on_tick(self._on_transport_tick)
        self.transport.on_beat(self._on_transport_beat)
        self.transport.on_bar(self._on_transport_bar)

        # OSC → Transport control
        self.osc.register("/transport/play", lambda _a, _args: asyncio.create_task(self.transport.start()))
        self.osc.register("/transport/stop", lambda _a, _args: asyncio.create_task(self.transport.stop()))
        self.osc.register("/transport/pause", lambda _a, _args: asyncio.create_task(self.transport.pause()))
        self.osc.register("/transport/bpm", lambda _a, args: setattr(self.transport, "bpm", float(args[0])))

        # OSC → Constraint host
        self.osc.register("/constraint/*/set/*", self._on_osc_constraint_set)
        self.osc.register("/constraint/*/trigger", self._on_osc_constraint_trigger)

        # Constraint host → OSC
        self.host.on_event(self._on_pipeline_event)

    def _on_transport_tick(self, tick: int, now: float) -> None:
        self.midi_clock.send_clock()
        self.osc.send_tick(tick)
        beat = self.transport.beat_count
        bar = self.transport.bar_count
        self.host.on_tick(tick, self.transport.bpm, beat, bar)

    def _on_transport_beat(self, beat: int, now: float) -> None:
        self.osc.send_beat(beat)

    def _on_transport_bar(self, bar: int, now: float) -> None:
        self.osc.send_bar(bar)

    def _on_osc_constraint_set(self, address: str, args: List[float]) -> None:
        parts = address.split("/")
        if len(parts) >= 5 and args:
            name = parts[2]
            param = parts[4]
            self.host.set_param(name, param, float(args[0]))

    def _on_osc_constraint_trigger(self, address: str, args: List[float]) -> None:
        parts = address.split("/")
        if len(parts) >= 3:
            name = parts[2]
            self.host.trigger(name)

    def _on_pipeline_event(self, ev: PipelineEvent) -> None:
        for midi in ev.midi_events:
            self.osc.send_note_on(midi.note, midi.velocity, midi.channel)
            # Schedule note_off via asyncio (best-effort)
            asyncio.create_task(self._delayed_note_off(midi.note, midi.duration_ms, midi.channel))

    async def _delayed_note_off(self, note: int, duration_ms: float, channel: int) -> None:
        await asyncio.sleep(duration_ms / 1000.0)
        self.osc.send_note_off(note, channel)

    async def start(self) -> None:
        self.midi_clock.open()
        await self.osc.start()
        self.midi_clock.send_start()
        await self.transport.start()

    async def stop(self) -> None:
        await self.transport.stop()
        self.midi_clock.send_stop()
        await self.osc.stop()
        self.midi_clock.close()

    async def pause(self) -> None:
        await self.transport.pause()
        self.midi_clock.send_stop()

    async def continue_(self) -> None:
        self.midi_clock.send_continue()
        await self.transport.continue_()

    def __repr__(self) -> str:
        return (
            f"Session(bpm={self.transport.bpm}, state={self.transport.state.name}, "
            f"pipelines={self.host.pipeline_names})"
        )
