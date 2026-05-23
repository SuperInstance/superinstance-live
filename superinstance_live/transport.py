"""Transport layer — single source of truth for time."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List


class TransportState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass
class TimeSignature:
    numerator: int = 4
    denominator: int = 4

    def __post_init__(self) -> None:
        if self.numerator < 1:
            raise ValueError(f"numerator must be >= 1, got {self.numerator}")
        if self.denominator < 1:
            raise ValueError(f"denominator must be >= 1, got {self.denominator}")

    def beats_per_bar(self) -> int:
        return self.numerator


TickCallback = Callable[[int, float], None]
BeatCallback = Callable[[int, float], None]
BarCallback = Callable[[int, float], None]


class Transport:
    """Async transport: play/stop/pause, BPM, time signature.

    Emits tick callbacks at 24 PPQN (MIDI clock resolution).
    Transport time is the single source of truth.
    """

    PPQN = 24

    def __init__(
        self,
        bpm: float = 120.0,
        time_signature: TimeSignature | None = None,
    ):
        if bpm <= 0:
            raise ValueError(f"bpm must be positive, got {bpm}")
        self._bpm = bpm
        self._time_signature = time_signature or TimeSignature()
        self._state = TransportState.STOPPED
        self._tick_count = 0
        self._beat_count = 0
        self._bar_count = 0
        self._start_time: float = 0.0
        self._pause_time: float = 0.0
        self._tick_callbacks: List[TickCallback] = []
        self._beat_callbacks: List[BeatCallback] = []
        self._bar_callbacks: List[BarCallback] = []
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    # ---- properties ----

    @property
    def bpm(self) -> float:
        return self._bpm

    @bpm.setter
    def bpm(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f"bpm must be positive, got {value}")
        self._bpm = value

    @property
    def state(self) -> TransportState:
        return self._state

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def beat_count(self) -> int:
        return self._beat_count

    @property
    def bar_count(self) -> int:
        return self._bar_count

    @property
    def time_signature(self) -> TimeSignature:
        return self._time_signature

    @time_signature.setter
    def time_signature(self, ts: TimeSignature) -> None:
        self._time_signature = ts

    def pulse_interval_s(self) -> float:
        """Seconds between 24-PPQN clock pulses."""
        return 60.0 / (self._bpm * self.PPQN)

    def beat_duration_s(self) -> float:
        return 60.0 / self._bpm

    # ---- callbacks ----

    def on_tick(self, cb: TickCallback) -> None:
        self._tick_callbacks.append(cb)

    def on_beat(self, cb: BeatCallback) -> None:
        self._beat_callbacks.append(cb)

    def on_bar(self, cb: BarCallback) -> None:
        self._bar_callbacks.append(cb)

    def remove_tick_callback(self, cb: TickCallback) -> None:
        if cb in self._tick_callbacks:
            self._tick_callbacks.remove(cb)

    # ---- control ----

    async def start(self) -> None:
        if self._state == TransportState.PLAYING:
            return
        if self._state == TransportState.STOPPED:
            self._tick_count = 0
            self._beat_count = 0
            self._bar_count = 0
        self._state = TransportState.PLAYING
        self._start_time = time.monotonic()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        self._state = TransportState.STOPPED
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=1.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None

    async def pause(self) -> None:
        if self._state != TransportState.PLAYING:
            return
        self._state = TransportState.PAUSED
        self._pause_time = time.monotonic()
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=1.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None

    async def continue_(self) -> None:
        if self._state != TransportState.PAUSED:
            return
        paused_duration = time.monotonic() - self._pause_time
        self._start_time += paused_duration
        self._state = TransportState.PLAYING
        self._stop_event.clear()
        self._task = asyncio.create_task(self._tick_loop())

    def reset(self) -> None:
        self._tick_count = 0
        self._beat_count = 0
        self._bar_count = 0
        if self._state == TransportState.STOPPED:
            self._start_time = 0.0

    # ---- internal ----

    async def _tick_loop(self) -> None:
        """High-resolution tick loop using asyncio sleep."""
        while self._state == TransportState.PLAYING and not self._stop_event.is_set():
            loop_start = time.monotonic()
            await self._do_tick()
            elapsed = time.monotonic() - loop_start
            sleep_time = self.pulse_interval_s() - elapsed
            if sleep_time > 0:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=sleep_time
                    )
                except asyncio.TimeoutError:
                    pass

    async def _do_tick(self) -> None:
        self._tick_count += 1
        now = time.monotonic()
        tick = self._tick_count

        # Beat detection
        beat_triggered = False
        if tick % self.PPQN == 0:
            self._beat_count += 1
            beat_triggered = True

        # Bar detection
        bar_triggered = False
        beats_per_bar = self._time_signature.beats_per_bar()
        if beat_triggered and (self._beat_count - 1) % beats_per_bar == 0:
            self._bar_count += 1
            bar_triggered = True

        for cb in list(self._tick_callbacks):
            try:
                cb(tick, now)
            except Exception:
                pass

        if beat_triggered:
            for cb in list(self._beat_callbacks):
                try:
                    cb(self._beat_count, now)
                except Exception:
                    pass

        if bar_triggered:
            for cb in list(self._bar_callbacks):
                try:
                    cb(self._bar_count, now)
                except Exception:
                    pass

    def __repr__(self) -> str:
        return (
            f"Transport(bpm={self._bpm}, state={self._state.name}, "
            f"ticks={self._tick_count}, beats={self._beat_count}, bars={self._bar_count})"
        )
