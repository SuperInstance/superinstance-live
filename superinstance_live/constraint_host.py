"""Loads constraint pipelines, feeds them transport state."""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from flux_tensor_midi.core.clock import TZeroClock
from flux_tensor_midi.core.room import RoomMusician
from flux_tensor_midi.core.snap import RhythmicRole
from flux_tensor_midi.midi.events import MidiEvent
from counterpoint_engine.generator import CounterpointGenerator, Species, Scale, VoiceRange
from counterpoint_engine.tensor_output import voices_to_tensor_events, TensorMIDIEvent
from groove_analyzer.deadband_groove import EnsembleFunnel, build_funnel
from groove_analyzer.microtiming import GrooveTiming


@dataclass
class PipelineEvent:
    """Event produced by a constraint pipeline."""
    source: str
    midi_events: List[MidiEvent] = field(default_factory=list)
    tensor_events: List[TensorMIDIEvent] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


PipelineCallback = Callable[[PipelineEvent], None]


class ConstraintPipeline(abc.ABC):
    """Abstract base for a constraint pipeline."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @abc.abstractmethod
    def on_tick(self, tick: int, bpm: float, beat: int, bar: int) -> Optional[PipelineEvent]:
        """Called on every transport tick. Return events or None."""
        ...

    @abc.abstractmethod
    def set_param(self, param: str, value: float) -> None:
        ...

    @abc.abstractmethod
    def trigger(self) -> None:
        ...

    @abc.abstractmethod
    def reset(self) -> None:
        ...


class FluxRoomPipeline(ConstraintPipeline):
    """Pipeline wrapping a flux-tensor-midi RoomMusician."""

    def __init__(self, name: str, role: RhythmicRole = RhythmicRole.ROOT, bpm: float = 120.0):
        self._name = name
        self._clock = TZeroClock(bpm=bpm)
        self._room = RoomMusician(name, role=role, clock=self._clock)
        self._events: List[PipelineEvent] = []

    @property
    def name(self) -> str:
        return self._name

    def on_tick(self, tick: int, bpm: float, beat: int, bar: int) -> Optional[PipelineEvent]:
        self._clock.set_bpm(bpm)
        # Emit a flux event every 24 ticks (1 beat)
        if tick > 0 and tick % 24 == 0:
            ts, vec = self._room.emit()
            midi_events = MidiEvent.from_flux(
                tuple(vec.values) if hasattr(vec, "values") else tuple(vec._values),
                start_ms=ts,
                duration_ms=(60000.0 / bpm),
                channel=0,
            )
            ev = PipelineEvent(source=self._name, midi_events=midi_events)
            self._events.append(ev)
            return ev
        return None

    def set_param(self, param: str, value: float) -> None:
        if param == "bpm":
            self._clock.set_bpm(value)
        elif param == "alpha":
            self._clock = TZeroClock(alpha=value, bpm=self._clock.bpm)
            self._room = RoomMusician(self._name, role=self._room.role, clock=self._clock)

    def trigger(self) -> None:
        pass

    def reset(self) -> None:
        self._clock.reset()
        self._events.clear()


class CounterpointPipeline(ConstraintPipeline):
    """Pipeline wrapping counterpoint-engine generation."""

    def __init__(
        self,
        name: str = "counterpoint",
        cantus_firmus: Optional[List[int]] = None,
        species: Species = Species.FIRST,
        scale: Optional[Scale] = None,
        voice_range: Optional[VoiceRange] = None,
    ):
        self._name = name
        self._cantus_firmus = cantus_firmus or [60, 62, 64, 65, 64, 62, 60]
        self._species = species
        self._scale = scale or Scale()
        self._voice_range = voice_range or VoiceRange()
        self._generator: Optional[CounterpointGenerator] = None
        self._result: Optional[Any] = None
        self._beat_index = 0
        self._midi_events: List[MidiEvent] = []
        self._tensor_events: List[TensorMIDIEvent] = []
        self._regenerate()

    def _regenerate(self) -> None:
        self._generator = CounterpointGenerator(
            cantus_firmus=self._cantus_firmus,
            species=self._species,
            scale=self._scale,
            voice_range=self._voice_range,
        )
        self._result = self._generator.generate()
        if self._result and self._result.feasible:
            try:
                tens, midi = voices_to_tensor_events(
                    self._result.voices,
                    beat_duration_ms=500.0,
                    velocity=100,
                )
                self._tensor_events = list(tens)
                self._midi_events = list(midi)
            except ValueError:
                # Voices may have unequal lengths for species 2+
                self._tensor_events = []
                self._midi_events = []
                # Build simple midi events from first voice
                for i, note in enumerate(self._result.voices[0]):
                    self._midi_events.append(
                        MidiEvent(
                            note=note,
                            velocity=100,
                            start_ms=i * 500.0,
                            duration_ms=500.0,
                            channel=0,
                        )
                    )
        else:
            self._tensor_events = []
            self._midi_events = []
        self._beat_index = 0

    @property
    def name(self) -> str:
        return self._name

    def on_tick(self, tick: int, bpm: float, beat: int, bar: int) -> Optional[PipelineEvent]:
        # Advance on beat boundaries
        if tick % 24 != 0:
            return None
        idx = (beat - 1) % max(len(self._cantus_firmus), 1)
        events: List[MidiEvent] = []
        tens: List[TensorMIDIEvent] = []
        for ev in self._midi_events:
            ev_beat = int(ev.start_ms // 500.0)
            if ev_beat == idx:
                events.append(ev)
        for tev in self._tensor_events:
            if tev.beat_k == idx:
                tens.append(tev)
        if events or tens:
            return PipelineEvent(source=self._name, midi_events=events, tensor_events=tens)
        return None

    def set_param(self, param: str, value: float) -> None:
        if param == "species":
            self._species = Species(int(value))
            self._regenerate()
        elif param == "tonic":
            self._scale = Scale(tonic=int(value) % 12)
            self._regenerate()

    def trigger(self) -> None:
        self._regenerate()

    def reset(self) -> None:
        self._beat_index = 0


class GroovePipeline(ConstraintPipeline):
    """Pipeline wrapping groove-analyzer deadband funnel."""

    def __init__(self, name: str = "groove", timing: Optional[GrooveTiming] = None):
        self._name = name
        self._timing = timing
        self._funnel: Optional[EnsembleFunnel] = None
        self._beat_index = 0
        if timing:
            self._funnel = build_funnel(timing)

    @property
    def name(self) -> str:
        return self._name

    def on_tick(self, tick: int, bpm: float, beat: int, bar: int) -> Optional[PipelineEvent]:
        if tick % 24 != 0:
            return None
        meta: Dict[str, Any] = {"beat": beat}
        if self._funnel:
            # Report current funnel phase for each player
            phases = {}
            for player, states in self._funnel.player_funnels.items():
                if states:
                    idx = (beat - 1) % len(states)
                    phases[player] = states[idx].phase
            meta["phases"] = phases
            meta["deadband_ms"] = self._funnel.deadband_ms
        return PipelineEvent(source=self._name, meta=meta)

    def set_param(self, param: str, value: float) -> None:
        if param == "decay_rate" and self._timing:
            self._funnel = build_funnel(self._timing, decay_rate=value)

    def trigger(self) -> None:
        pass

    def reset(self) -> None:
        self._beat_index = 0


class ConstraintHost:
    """Host for constraint pipelines — receives transport ticks, produces events."""

    def __init__(self):
        self._pipelines: Dict[str, ConstraintPipeline] = {}
        self._callbacks: List[PipelineCallback] = []
        self._muted: set[str] = set()

    def add_pipeline(self, pipeline: ConstraintPipeline) -> None:
        self._pipelines[pipeline.name] = pipeline

    def remove_pipeline(self, name: str) -> None:
        self._pipelines.pop(name, None)

    def get_pipeline(self, name: str) -> Optional[ConstraintPipeline]:
        return self._pipelines.get(name)

    def on_event(self, cb: PipelineCallback) -> None:
        self._callbacks.append(cb)

    def mute(self, name: str) -> None:
        self._muted.add(name)

    def unmute(self, name: str) -> None:
        self._muted.discard(name)

    def on_tick(self, tick: int, bpm: float, beat: int, bar: int) -> List[PipelineEvent]:
        events: List[PipelineEvent] = []
        for name, pipeline in self._pipelines.items():
            if name in self._muted:
                continue
            ev = pipeline.on_tick(tick, bpm, beat, bar)
            if ev:
                events.append(ev)
                for cb in list(self._callbacks):
                    try:
                        cb(ev)
                    except Exception:
                        pass
        return events

    def set_param(self, name: str, param: str, value: float) -> None:
        p = self._pipelines.get(name)
        if p:
            p.set_param(param, value)

    def trigger(self, name: str) -> None:
        p = self._pipelines.get(name)
        if p:
            p.trigger()

    def reset_all(self) -> None:
        for p in self._pipelines.values():
            p.reset()

    @property
    def pipeline_names(self) -> List[str]:
        return list(self._pipelines.keys())

    def __repr__(self) -> str:
        return f"ConstraintHost(pipelines={self.pipeline_names})"
