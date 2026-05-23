"""Tests for midi_clock module."""

import pytest
from superinstance_live.midi_clock import MidiClockOut


class TestMidiClockOut:
    def test_init(self):
        mc = MidiClockOut()
        assert mc.tick_count == 0
        assert not mc._running

    def test_send_clock_advances_tick(self):
        mc = MidiClockOut()
        mc.send_clock()
        assert mc.tick_count == 1
        assert mc._running

    def test_beat_calculation(self):
        mc = MidiClockOut()
        for _ in range(48):
            mc.send_clock()
        assert mc.beat() == 2

    def test_tick_in_beat(self):
        mc = MidiClockOut()
        for _ in range(25):
            mc.send_clock()
        assert mc.tick_in_beat() == 1

    def test_start_resets_ticks(self):
        mc = MidiClockOut()
        mc.send_clock()
        mc.send_start()
        assert mc.tick_count == 0

    def test_stop_sets_not_running(self):
        mc = MidiClockOut()
        mc.send_clock()
        mc.send_stop()
        assert not mc._running

    def test_tick_callback(self):
        ticks = []
        mc = MidiClockOut()
        mc.on_tick(lambda t: ticks.append(t))
        mc.send_clock()
        mc.send_clock()
        assert ticks == [1, 2]
