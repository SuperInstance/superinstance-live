"""Extended tests for midi_clock module."""

import pytest
from superinstance_live.midi_clock import MidiClockOut


class TestMidiClockOutExtended:
    def test_init_with_port_name(self):
        mc = MidiClockOut(port_name="test_port")
        assert mc._port_name == "test_port"
        assert mc.tick_count == 0

    def test_init_virtual(self):
        mc = MidiClockOut(virtual=True)
        assert mc._virtual is True

    def test_send_continue_sets_running(self):
        mc = MidiClockOut()
        mc.send_continue()
        assert mc._running is True

    def test_send_clock_multiple(self):
        mc = MidiClockOut()
        for i in range(100):
            mc.send_clock()
        assert mc.tick_count == 100
        assert mc.beat() == 4  # 100 // 24
        assert mc.tick_in_beat() == 4  # 100 % 24

    def test_start_then_clock(self):
        mc = MidiClockOut()
        mc.send_start()
        assert mc.tick_count == 0
        mc.send_clock()
        assert mc.tick_count == 1

    def test_beat_boundary(self):
        mc = MidiClockOut()
        for _ in range(23):
            mc.send_clock()
        assert mc.beat() == 0
        mc.send_clock()  # 24th tick
        assert mc.beat() == 1

    def test_tick_in_beat_wraps(self):
        mc = MidiClockOut()
        for _ in range(24):
            mc.send_clock()
        assert mc.tick_in_beat() == 0

    def test_stop_after_running(self):
        mc = MidiClockOut()
        mc.send_clock()
        mc.send_clock()
        assert mc._running
        mc.send_stop()
        assert not mc._running

    def test_multiple_callbacks(self):
        mc = MidiClockOut()
        a, b = [], []
        mc.on_tick(lambda t: a.append(t))
        mc.on_tick(lambda t: b.append(t))
        mc.send_clock()
        assert a == [1]
        assert b == [1]

    def test_callback_exception_swallowed(self):
        mc = MidiClockOut()
        results = []

        def bad(t):
            raise RuntimeError("fail")

        def good(t):
            results.append(t)

        mc.on_tick(bad)
        mc.on_tick(good)
        mc.send_clock()
        assert results == [1]

    def test_open_no_port_does_not_crash(self):
        mc = MidiClockOut()
        mc.open()  # No hardware available in CI; should not crash

    def test_close_without_open(self):
        mc = MidiClockOut()
        mc.close()  # should not raise

    def test_repr(self):
        mc = MidiClockOut(port_name="test")
        r = repr(mc)
        assert "MidiClockOut" in r
        assert "test" in r

    def test_start_resets_tick_count(self):
        mc = MidiClockOut()
        for _ in range(50):
            mc.send_clock()
        assert mc.tick_count == 50
        mc.send_start()
        assert mc.tick_count == 0
