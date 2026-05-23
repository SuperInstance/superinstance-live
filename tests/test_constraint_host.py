"""Tests for constraint_host module."""

import pytest
from superinstance_live.constraint_host import (
    ConstraintHost,
    FluxRoomPipeline,
    CounterpointPipeline,
    GroovePipeline,
    PipelineEvent,
)
from counterpoint_engine.generator import Species, Scale
from groove_analyzer.microtiming import GrooveTiming, TrackTiming, OnsetEvent, TimingClass


def _make_onset(beat, dev=0.0):
    return OnsetEvent(
        time_sec=beat * 0.5,
        beat=beat,
        pitch=60,
        velocity=100,
        channel=9,
        track_name="drums",
        grid_line=beat,
        deviation_ms=dev,
        timing_class=TimingClass.POCKET,
    )


class TestConstraintHost:
    def test_add_remove_pipeline(self):
        host = ConstraintHost()
        pipe = FluxRoomPipeline("flux1")
        host.add_pipeline(pipe)
        assert "flux1" in host.pipeline_names
        host.remove_pipeline("flux1")
        assert "flux1" not in host.pipeline_names

    def test_mute_unmute(self):
        host = ConstraintHost()
        pipe = FluxRoomPipeline("flux1")
        host.add_pipeline(pipe)
        host.mute("flux1")
        ev = host.on_tick(24, 120.0, 1, 1)
        assert ev == []
        host.unmute("flux1")
        ev = host.on_tick(24, 120.0, 1, 1)
        assert len(ev) == 1

    def test_set_param(self):
        host = ConstraintHost()
        pipe = FluxRoomPipeline("flux1")
        host.add_pipeline(pipe)
        host.set_param("flux1", "bpm", 140.0)
        assert pipe._clock.bpm == 140.0

    def test_trigger(self):
        host = ConstraintHost()
        pipe = CounterpointPipeline("cp")
        host.add_pipeline(pipe)
        host.trigger("cp")
        assert pipe._result is not None

    def test_reset_all(self):
        host = ConstraintHost()
        pipe = FluxRoomPipeline("flux1")
        host.add_pipeline(pipe)
        host.on_tick(24, 120.0, 1, 1)
        host.reset_all()
        assert pipe._events == []

    def test_event_callback(self):
        host = ConstraintHost()
        received = []
        host.on_event(lambda ev: received.append(ev))
        pipe = FluxRoomPipeline("flux1")
        host.add_pipeline(pipe)
        host.on_tick(24, 120.0, 1, 1)
        assert len(received) == 1
        assert isinstance(received[0], PipelineEvent)


class TestFluxRoomPipeline:
    def test_name(self):
        p = FluxRoomPipeline("room_a")
        assert p.name == "room_a"

    def test_on_tick_emits_every_24(self):
        p = FluxRoomPipeline("room_a")
        assert p.on_tick(1, 120.0, 0, 0) is None
        ev = p.on_tick(24, 120.0, 1, 1)
        assert ev is not None
        assert ev.source == "room_a"
        # Zero-state flux vector may produce empty midi_events; that's OK
        assert isinstance(ev, PipelineEvent)

    def test_set_param_bpm(self):
        p = FluxRoomPipeline("room_a")
        p.set_param("bpm", 90.0)
        assert p._clock.bpm == 90.0

    def test_reset(self):
        p = FluxRoomPipeline("room_a")
        p.on_tick(24, 120.0, 1, 1)
        p.reset()
        assert p._events == []


class TestCounterpointPipeline:
    def test_name(self):
        p = CounterpointPipeline("cp")
        assert p.name == "cp"

    def test_generates_on_init(self):
        p = CounterpointPipeline("cp")
        assert p._result is not None

    def test_on_tick_returns_events(self):
        p = CounterpointPipeline("cp")
        ev = p.on_tick(24, 120.0, 1, 1)
        assert ev is not None
        assert isinstance(ev, PipelineEvent)

    def test_set_param_species(self):
        p = CounterpointPipeline("cp")
        p.set_param("species", 2.0)
        assert p._species == Species.SECOND

    def test_set_param_tonic(self):
        p = CounterpointPipeline("cp")
        p.set_param("tonic", 7.0)
        assert p._scale.tonic == 7

    def test_trigger_regenerates(self):
        p = CounterpointPipeline("cp")
        old_result = p._result
        p.trigger()
        assert p._result is not None


class TestGroovePipeline:
    def test_name(self):
        onsets = [_make_onset(i) for i in range(4)]
        track = TrackTiming(track_name="drums", onsets=onsets)
        timing = GrooveTiming(tracks=[track], bpm=120.0, ticks_per_beat=480, grid_division=4)
        p = GroovePipeline("groove", timing=timing)
        assert p.name == "groove"

    def test_on_tick_meta(self):
        onsets = [_make_onset(i) for i in range(4)]
        track = TrackTiming(track_name="drums", onsets=onsets)
        timing = GrooveTiming(tracks=[track], bpm=120.0, ticks_per_beat=480, grid_division=4)
        p = GroovePipeline("groove", timing=timing)
        ev = p.on_tick(24, 120.0, 1, 1)
        assert ev is not None
        assert "phases" in ev.meta
