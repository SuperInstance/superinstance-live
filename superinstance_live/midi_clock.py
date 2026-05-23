"""MIDI Clock generator (24 PPQN) via mido."""

from __future__ import annotations

from typing import Callable, List

import mido


class MidiClockOut:
    """Generate MIDI Clock messages (0xF8) and transport control.

    Parameters
    ----------
    port_name : str | None
        mido output port name. If None, uses mido.open_output() default.
    virtual : bool
        If True, create a virtual port (platform-dependent).
    """

    CLOCK = 0xF8
    START = 0xFA
    STOP = 0xFC
    CONTINUE = 0xFB

    def __init__(self, port_name: str | None = None, virtual: bool = False):
        self._port_name = port_name
        self._virtual = virtual
        self._port: mido.ports.BaseOutput | None = None
        self._tick_callbacks: List[Callable[[int], None]] = []
        self._tick_count = 0
        self._running = False

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def on_tick(self, cb: Callable[[int], None]) -> None:
        self._tick_callbacks.append(cb)

    def open(self) -> None:
        if self._port is not None:
            return
        try:
            if self._virtual:
                self._port = mido.open_output(self._port_name or "superinstance-live", virtual=True)
            else:
                self._port = mido.open_output(self._port_name)
        except Exception:
            # Fallback: no hardware port available (e.g. CI, headless)
            self._port = None

    def close(self) -> None:
        if self._port:
            self._port.close()
            self._port = None

    def send_start(self) -> None:
        self._send_byte(self.START)
        self._tick_count = 0

    def send_stop(self) -> None:
        self._send_byte(self.STOP)
        self._running = False

    def send_continue(self) -> None:
        self._send_byte(self.CONTINUE)
        self._running = True

    def send_clock(self) -> None:
        self._send_byte(self.CLOCK)
        self._tick_count += 1
        self._running = True
        for cb in list(self._tick_callbacks):
            try:
                cb(self._tick_count)
            except Exception:
                pass

    def _send_byte(self, status: int) -> None:
        if self._port:
            self._port.send(mido.Message("clock", clks=status))

    def beat(self) -> int:
        """Current beat number (1 beat = 24 ticks)."""
        return self._tick_count // 24

    def tick_in_beat(self) -> int:
        return self._tick_count % 24

    def __repr__(self) -> str:
        return (
            f"MidiClockOut(port={self._port_name!r}, "
            f"running={self._running}, ticks={self._tick_count})"
        )
