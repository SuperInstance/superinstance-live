"""Extended tests for constraint_host — custom pipelines, host edge cases."""

import pytest
from superinstance_live.constraint_host import (
    ConstraintHost,
    ConstraintPipeline,
    PipelineEvent,
    FluxRoomPipeline,
    CounterpointPipeline,
    GroovePipeline,
)
from typing import Optional, Dict, Any, List


# ---- Custom pipeline for testing the ABC ----


class DummyPipeline(ConstraintPipeline):
    """Minimal concrete pipeline for testing."""

    def __init__(self, name: str = "dummy"):
        self._name = name
        self._params: Dict[str, float] = {}
        self._triggered = 0
        self._reset_count = 0

    @property
    def name(self) -> str:
        return self._name

    def on_tick(self, tick: int, bpm: float, beat: int, bar: int) -> Optional[PipelineEvent]:
        if tick % 12 == 0:
            return PipelineEvent(source=self._name, meta={"tick": tick, "bpm": bpm})
        return None

    def set_param(self, param: str, value: float) -> None:
        self._params[param] = value

    def trigger(self) -> None:
        self._triggered += 1

    def reset(self) -> None:
        self._reset_count += 1
        self._params.clear()


class TestConstraintPipelineABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ConstraintPipeline()

    def test_dummy_pipeline_name(self):
        p = DummyPipeline("test")
        assert p.name == "test"

    def test_dummy_pipeline_on_tick(self):
        p = DummyPipeline("test")
        assert p.on_tick(1, 120.0, 0, 0) is None
        ev = p.on_tick(12, 120.0, 0, 0)
        assert ev is not None
        assert ev.source == "test"
        assert ev.meta["tick"] == 12

    def test_dummy_set_param(self):
        p = DummyPipeline("test")
        p.set_param("alpha", 0.5)
        assert p._params["alpha"] == 0.5

    def test_dummy_trigger(self):
        p = DummyPipeline("test")
        p.trigger()
        assert p._triggered == 1
        p.trigger()
        assert p._triggered == 2

    def test_dummy_reset(self):
        p = DummyPipeline("test")
        p.set_param("x", 1.0)
        p.reset()
        assert p._params == {}
        assert p._reset_count == 1


class TestConstraintHostExtended:
    def test_empty_host(self):
        host = ConstraintHost()
        assert host.pipeline_names == []
        assert host.on_tick(1, 120.0, 0, 0) == []
        assert repr(host) == "ConstraintHost(pipelines=[])"

    def test_add_multiple_pipelines(self):
        host = ConstraintHost()
        host.add_pipeline(DummyPipeline("a"))
        host.add_pipeline(DummyPipeline("b"))
        assert set(host.pipeline_names) == {"a", "b"}

    def test_remove_nonexistent(self):
        host = ConstraintHost()
        host.remove_pipeline("ghost")  # should not raise

    def test_get_nonexistent(self):
        host = ConstraintHost()
        assert host.get_pipeline("ghost") is None

    def test_get_existing(self):
        host = ConstraintHost()
        p = DummyPipeline("x")
        host.add_pipeline(p)
        assert host.get_pipeline("x") is p

    def test_add_replaces_same_name(self):
        host = ConstraintHost()
        p1 = DummyPipeline("p")
        p2 = DummyPipeline("p")
        host.add_pipeline(p1)
        host.add_pipeline(p2)
        assert host.get_pipeline("p") is p2

    def test_mute_nonexistent(self):
        host = ConstraintHost()
        host.mute("nothing")  # should not raise

    def test_unmute_nonexistent(self):
        host = ConstraintHost()
        host.unmute("nothing")  # should not raise

    def test_on_tick_multiple_unmuted(self):
        host = ConstraintHost()
        host.add_pipeline(DummyPipeline("a"))
        host.add_pipeline(DummyPipeline("b"))
        evs = host.on_tick(12, 120.0, 0, 0)
        assert len(evs) == 2

    def test_on_tick_muted_skipped(self):
        host = ConstraintHost()
        host.add_pipeline(DummyPipeline("a"))
        host.add_pipeline(DummyPipeline("b"))
        host.mute("a")
        evs = host.on_tick(12, 120.0, 0, 0)
        assert len(evs) == 1
        assert evs[0].source == "b"

    def test_on_tick_partial_mute(self):
        host = ConstraintHost()
        host.add_pipeline(DummyPipeline("a"))
        host.add_pipeline(DummyPipeline("b"))
        host.mute("a")
        evs = host.on_tick(12, 120.0, 0, 0)
        sources = [e.source for e in evs]
        assert "a" not in sources
        assert "b" in sources

    def test_on_tick_no_events_for_non_matching_tick(self):
        host = ConstraintHost()
        host.add_pipeline(DummyPipeline("a"))
        evs = host.on_tick(1, 120.0, 0, 0)  # tick 1 not % 12
        assert evs == []

    def test_event_callback_receives_events(self):
        host = ConstraintHost()
        received = []
        host.on_event(lambda ev: received.append(ev))
        host.add_pipeline(DummyPipeline("a"))
        host.on_tick(12, 120.0, 0, 0)
        assert len(received) == 1
        assert received[0].source == "a"

    def test_multiple_event_callbacks(self):
        host = ConstraintHost()
        r1, r2 = [], []
        host.on_event(lambda ev: r1.append(ev))
        host.on_event(lambda ev: r2.append(ev))
        host.add_pipeline(DummyPipeline("a"))
        host.on_tick(12, 120.0, 0, 0)
        assert len(r1) == 1
        assert len(r2) == 1

    def test_event_callback_exception_swallowed(self):
        host = ConstraintHost()
        good = []
        host.on_event(lambda ev: 1 / 0)  # will raise
        host.on_event(lambda ev: good.append(ev))
        host.add_pipeline(DummyPipeline("a"))
        host.on_tick(12, 120.0, 0, 0)
        assert len(good) == 1  # good callback still works

    def test_set_param_on_nonexistent(self):
        host = ConstraintHost()
        host.set_param("ghost", "x", 1.0)  # should not raise

    def test_trigger_on_nonexistent(self):
        host = ConstraintHost()
        host.trigger("ghost")  # should not raise

    def test_reset_all(self):
        host = ConstraintHost()
        a = DummyPipeline("a")
        b = DummyPipeline("b")
        a.set_param("x", 1.0)
        b.set_param("y", 2.0)
        host.add_pipeline(a)
        host.add_pipeline(b)
        host.reset_all()
        assert a._reset_count == 1
        assert b._reset_count == 1

    def test_repr_with_pipelines(self):
        host = ConstraintHost()
        host.add_pipeline(DummyPipeline("foo"))
        r = repr(host)
        assert "ConstraintHost" in r
        assert "foo" in r


class TestPipelineEvent:
    def test_defaults(self):
        ev = PipelineEvent(source="test")
        assert ev.source == "test"
        assert ev.midi_events == []
        assert ev.tensor_events == []
        assert ev.meta == {}

    def test_custom(self):
        ev = PipelineEvent(
            source="x",
            midi_events=[1, 2],
            tensor_events=[3],
            meta={"key": "val"},
        )
        assert ev.midi_events == [1, 2]
        assert ev.tensor_events == [3]
        assert ev.meta["key"] == "val"


class TestCounterpointExtended:
    def test_on_tick_non_beat_returns_none(self):
        p = CounterpointPipeline("cp")
        assert p.on_tick(1, 120.0, 0, 0) is None

    def test_on_tick_wraps_around_cantus(self):
        p = CounterpointPipeline("cp")
        # beat indices wrap around
        for beat in range(1, 20):
            ev = p.on_tick(beat * 24, 120.0, beat, 0)
            # Should not crash even when beat > cantus length

    def test_trigger_produces_result(self):
        p = CounterpointPipeline("cp")
        p.trigger()
        assert p._result is not None

    def test_reset(self):
        p = CounterpointPipeline("cp")
        p.reset()
        assert p._beat_index == 0


class TestGrooveExtended:
    def test_on_tick_non_beat_returns_none(self):
        p = GroovePipeline("groove")
        assert p.on_tick(1, 120.0, 0, 0) is None

    def test_on_tick_without_timing(self):
        p = GroovePipeline("groove")
        ev = p.on_tick(24, 120.0, 1, 1)
        assert ev is not None
        assert "beat" in ev.meta

    def test_set_param_decay_no_timing(self):
        p = GroovePipeline("groove")
        p.set_param("decay_rate", 0.5)  # no timing, no-op

    def test_reset(self):
        p = GroovePipeline("groove")
        p.reset()
        assert p._beat_index == 0
