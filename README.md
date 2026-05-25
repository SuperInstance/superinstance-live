# superinstance-live

> DAW-agnostic session controller for constraint music systems.

`superinstance-live` orchestrates real-time musical constraint pipelines — flux tensor MIDI, counterpoint generation, and groove analysis — synchronized via an internal transport, MIDI Clock (24 PPQN), and bidirectional OSC. It's the runtime that ties the SuperInstance ecosystem together.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Session                          │
│                                                      │
│  ┌───────────┐   ┌──────────────┐   ┌────────────┐ │
│  │ Transport │──▶│ ConstraintHost│──▶│  MIDI Clock │ │
│  │ (24 PPQN) │   │              │   │  Out        │ │
│  └───────────┘   │  ┌─────────┐ │   └────────────┘ │
│       │          │  │ FluxRoom│ │                    │
│       │          │  ├─────────┤ │   ┌────────────┐ │
│       └─────────▶│  │Counterpt│ │──▶│OSC Bridge  │ │
│                  │  ├─────────┤ │   │(in + out)  │ │
│                  │  │ Groove  │ │   └────────────┘ │
│                  │  └─────────┘ │                    │
│                  └──────────────┘                    │
└─────────────────────────────────────────────────────┘
```

### Components

- **Transport** — Async, high-resolution time source at 24 PPQN. Emits tick/beat/bar callbacks. Supports play/stop/pause/continue.
- **ConstraintHost** — Manages multiple constraint pipelines, routes transport ticks to each, collects and dispatches events.
- **MidiClockOut** — Sends MIDI Clock (0xF8), Start (0xFA), Stop (0xFC), Continue (0xFB) via `mido`.
- **OSCBridge** — Bidirectional OSC via `python-osc`. Receives transport commands and constraint parameter changes; sends tick/beat/bar/note events.

### Constraint Pipelines

| Pipeline | Source Library | Description |
|---|---|---|
| `FluxRoomPipeline` | flux-tensor-midi | Room musician with rhythmic roles, emits flux tensor vectors every beat |
| `CounterpointPipeline` | counterpoint-engine | Species counterpoint generation over a cantus firmus |
| `GroovePipeline` | groove-analyzer | Deadband funnel tracking for microtiming analysis |

Custom pipelines can be created by implementing the `ConstraintPipeline` ABC.

## Installation

```bash
pip install superinstance-live
```

Requires Python ≥ 3.10, `mido` ≥ 1.3, `python-osc` ≥ 1.10.

## Quick Start

### CLI

```bash
# Start a session with default flux pipeline
superinstance-live start --bpm 120 --port 8000

# With counterpoint and groove pipelines
superinstance-live start --bpm 90 --counterpoint --groove

# Custom MIDI port
superinstance-live start --bpm 140 --midi-port "IAC Driver Bus 1"
```

### Python API

```python
import asyncio
from superinstance_live import Session

async def main():
    session = Session(bpm=120, osc_listen_port=8000, osc_send_port=9000)
    
    # Add constraint pipelines
    from superinstance_live.constraint_host import FluxRoomPipeline
    session.host.add_pipeline(FluxRoomPipeline("flux"))
    
    # Start
    await session.start()
    
    # Run for a while
    await asyncio.sleep(60)
    
    # Stop
    await session.stop()

asyncio.run(main())
```

### Transport

```python
from superinstance_live import Transport, TransportState

transport = Transport(bpm=140)

# Register callbacks
transport.on_tick(lambda tick, now: print(f"tick {tick}"))
transport.on_beat(lambda beat, now: print(f"beat {beat}"))
transport.on_bar(lambda bar, now: print(f"bar {bar}"))

# Control
await transport.start()
transport.bpm = 160  # change tempo live
await transport.pause()
await transport.continue_()
await transport.stop()
```

### OSC Protocol

**Received (from DAW/controller):**

| Address | Args | Description |
|---|---|---|
| `/transport/play` | — | Start transport |
| `/transport/stop` | — | Stop transport |
| `/transport/pause` | — | Pause transport |
| `/transport/bpm` | `f` | Set BPM |
| `/constraint/{name}/set/{param}` | `f` | Set pipeline parameter |
| `/constraint/{name}/trigger` | — | Trigger pipeline action |

**Sent (to DAW/controller):**

| Address | Args | Description |
|---|---|---|
| `/transport/tick` | `i` | Tick number |
| `/transport/beat` | `i` | Beat number |
| `/transport/bar` | `i` | Bar number |
| `/midi/note_on` | `i, i, i` | Note, velocity, channel |
| `/midi/note_off` | `i, i` | Note, channel |

### Custom Pipelines

```python
from superinstance_live.constraint_host import ConstraintPipeline, PipelineEvent

class MyPipeline(ConstraintPipeline):
    @property
    def name(self) -> str:
        return "custom"
    
    def on_tick(self, tick, bpm, beat, bar):
        if tick % 24 == 0:  # every beat
            return PipelineEvent(source="custom", meta={"beat": beat})
        return None
    
    def set_param(self, param, value):
        pass
    
    def trigger(self):
        pass
    
    def reset(self):
        pass

# Use it
session.host.add_pipeline(MyPipeline())
```

### ConstraintHost API

```python
host = session.host

# Manage pipelines
host.add_pipeline(pipeline)
host.remove_pipeline("name")
host.get_pipeline("name")

# Mute/unmute
host.mute("flux")
host.unmute("flux")

# Set parameters live
host.set_param("flux", "alpha", 0.7)
host.set_param("counterpoint", "species", 2.0)

# Trigger actions
host.trigger("counterpoint")

# Listen for events
host.on_event(lambda ev: print(ev.source, ev.midi_events))
```

## API Reference

### `Session`

```python
Session(bpm=120.0, osc_listen_port=8000, osc_send_port=9000, midi_port=None)
```

| Method | Description |
|---|---|
| `await .start()` | Start transport, MIDI clock, OSC server |
| `await .stop()` | Stop everything |
| `await .pause()` | Pause transport + MIDI clock |
| `await .continue_()` | Resume from paused state |
| `.host` | `ConstraintHost` instance |
| `.transport` | `Transport` instance |
| `.midi_clock` | `MidiClockOut` instance |
| `.osc` | `OSCBridge` instance |

### `Transport`

```python
Transport(bpm=120.0, time_signature=TimeSignature(4, 4))
```

| Property | Description |
|---|---|
| `.bpm` | Current BPM (settable) |
| `.state` | `TransportState.STOPPED/PLAYING/PAUSED` |
| `.tick_count` | Total ticks since start |
| `.beat_count` | Total beats since start |
| `.bar_count` | Total bars since start |
| `.time_signature` | `TimeSignature` (settable) |

| Method | Description |
|---|---|
| `.on_tick(cb)` | Register tick callback `(tick, now)` |
| `.on_beat(cb)` | Register beat callback `(beat, now)` |
| `.on_bar(cb)` | Register bar callback `(bar, now)` |
| `.pulse_interval_s()` | Seconds between 24-PPQN pulses |
| `.beat_duration_s()` | Seconds per beat |

### `ConstraintHost`

| Method | Description |
|---|---|
| `.add_pipeline(pipeline)` | Add a constraint pipeline |
| `.remove_pipeline(name)` | Remove by name |
| `.get_pipeline(name)` | Get pipeline by name |
| `.on_event(cb)` | Register event callback |
| `.mute(name)` / `.unmute(name)` | Mute/unmute a pipeline |
| `.set_param(name, param, value)` | Set pipeline parameter |
| `.trigger(name)` | Trigger pipeline action |
| `.reset_all()` | Reset all pipelines |
| `.pipeline_names` | List of active pipeline names |

### `OSCBridge`

```python
OSCBridge(listen_host="127.0.0.1", listen_port=8000, send_host="127.0.0.1", send_port=9000)
```

| Method | Description |
|---|---|
| `.register(address, handler)` | Register OSC handler |
| `.send(address, *values)` | Send OSC message |
| `.send_tick(tick)` | Send tick event |
| `.send_beat(beat)` | Send beat event |
| `.send_bar(bar)` | Send bar event |
| `.send_note_on(note, vel, ch)` | Send note on |
| `.send_note_off(note, ch)` | Send note off |

### `MidiClockOut`

```python
MidiClockOut(port_name=None, virtual=False)
```

| Method | Description |
|---|---|
| `.open()` | Open MIDI output port |
| `.close()` | Close port |
| `.send_start()` | MIDI Start (0xFA) |
| `.send_stop()` | MIDI Stop (0xFC) |
| `.send_continue()` | MIDI Continue (0xFB) |
| `.send_clock()` | MIDI Clock tick (0xF8) |

## Related Repos

- **[constraint-toolkit](https://github.com/SuperInstance/constraint-toolkit)** — Core constraint theory library
- **[constraint-dsl](https://github.com/SuperInstance/constraint-dsl)** — Declarative YAML language for constraint pipelines
- **[flux-genome](https://github.com/SuperInstance/flux-genome)** — Genetic algorithm framework for evolving traditions
- **[plato-client](https://github.com/SuperInstance/plato-client)** — Client for the Plato optimization backend
- **[plato-adapters](https://github.com/SuperInstance/plato-adapters)** — Adapters for Plato integration

## License

MIT
