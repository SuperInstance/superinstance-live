# superinstance-live

> DAW-agnostic session controller for live constraint-driven music performance

Part of the [SuperInstance](https://github.com/SuperInstance) music constraint theory ecosystem. Provides a real-time session manager that bridges constraint satisfaction engines with any DAW or hardware setup via MIDI clock, OSC, and a pluggable host architecture. Write your constraints once, perform anywhere.

## What It Does

Live music performance with constraint systems requires a coordinator that manages tempo, synchronizes transport, routes constraints to the right voices, and keeps everything running in real-time. **superinstance-live** is that coordinator. It provides a DAW-agnostic session model — you define your constraint pipeline (via [constraint-dsl](https://github.com/SuperInstance/constraint-dsl)), configure your outputs (MIDI, OSC, or both), and the session controller handles tempo mapping, beat alignment, and constraint evaluation on every tick.

The transport supports play/pause/stop with tempo tracking. The MIDI clock generator keeps external hardware in sync. The OSC bridge communicates with DAWs and visual tools. The constraint host loads and evaluates constraint pipelines on each musical step.

## Key Features

- **DAW-agnostic transport** — play, pause, stop, tempo, time signature — works with anything
- **MIDI clock generator** — sends MIDI clock pulses to keep hardware in sync
- **OSC bridge** — bidirectional OSC communication with DAWs and visual tools
- **Constraint host** — loads and evaluates constraint-toolkit pipelines per step
- **Session model** — scenes, patterns, tracks — organized for live performance
- **CLI interface** — command-line control for headless operation

## Installation

```bash
git clone https://github.com/SuperInstance/superinstance-live.git
cd superinstance-live
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Quick Start

### Start a session

```python
from superinstance_live import Session, Transport, ConstraintHost
from constraint_dsl import parse, compile_pipeline

# Load a constraint pipeline
pipeline = compile_pipeline(parse("jazz_solo.yaml"))

# Set up the session
transport = Transport(bpm=120, time_signature=(4, 4))
host = ConstraintHost(pipeline)
session = Session(transport=transport, constraint_host=host)

# Start playback
session.play()

# Each tick: transport advances, constraints evaluate, output fires
for step in session.steps():
    midi_events = step.midi_output
    osc_messages = step.osc_output
```

### MIDI clock output

```python
from superinstance_live import MIDIClock

clock = MIDIClock(bpm=120, midi_port="IAC Driver - Bus 1")
clock.start()

# Sends clock pulses at the right intervals
# Compatible with any MIDI hardware
```

### OSC bridge

```python
from superinstance_live import OSCBridge

bridge = OSCBridge(
    send_host="127.0.0.1",
    send_port=9000,
    receive_host="127.0.0.1",
    receive_port=9001,
)

# Send to DAW
bridge.send("/transport/play", tempo=120)

# Receive from DAW
@bridge.on("/clip/launched")
def on_clip_launched(path, args):
    print(f"Clip launched: {args}")
```

### CLI control

```bash
# Start a headless session
superinstance-live --pipeline jazz_solo.yaml --bpm 120 --midi-out "IAC Bus 1"

# With OSC
superinstance-live --pipeline trap_beat.yaml --bpm 140 --osc-send 127.0.0.1:9000
```

## Architecture

```
superinstance_live/
├── session.py        # Session controller (top-level coordinator)
├── transport.py      # Transport state (play/pause/stop/tempo)
├── midi_clock.py     # MIDI clock pulse generator
├── osc_bridge.py     # Bidirectional OSC communication
├── constraint_host.py # Constraint pipeline evaluator
└── cli.py            # Command-line interface
```

### Session Flow

```
Transport tick → Constraint evaluation → Voice assignment → MIDI + OSC output
       ↑                                                        |
       └──────────── tempo feedback from external clock ────────┘
```

## API Reference

### `Session`

```python
session = Session(transport, constraint_host, midi_output=None, osc_bridge=None)
session.play()               # Start playback
session.pause()              # Pause (maintains position)
session.stop()               # Stop (reset to beginning)
session.steps()              # Iterator yielding SessionStep objects
session.current_step         # Current step number
session.tempo                # Current BPM
```

### `Transport`

```python
transport = Transport(bpm=120, time_signature=(4, 4))
transport.bpm = 140          # Change tempo
transport.position           # (bar, beat, tick) tuple
transport.advance()          # Move forward one tick
```

### `ConstraintHost`

```python
host = ConstraintHost(pipeline)
result = host.evaluate(context)  # Evaluate constraints for current context
```

### `MIDIClock`

```python
clock = MIDIClock(bpm, midi_port)
clock.start()
clock.stop()
clock.tempo = 130  # Update tempo live
```

### `OSCBridge`

```python
bridge = OSCBridge(send_host, send_port, receive_host, receive_port)
bridge.send(address, **args)
bridge.on(address)(handler)  # Register handler
```

## Testing

```bash
pytest                            # Run all tests
pytest tests/test_transport.py    # Transport tests
pytest tests/test_midi_clock.py   # MIDI clock timing tests
pytest tests/test_osc_bridge.py   # OSC communication tests
```

## Related Repos

- [**constraint-dsl**](https://github.com/SuperInstance/constraint-dsl) — Define the constraint pipelines this controller runs
- [**constraint-toolkit**](https://github.com/SuperInstance/constraint-toolkit) — Constraint satisfaction engine used by the host
- [**flux-genome**](https://github.com/SuperInstance/flux-genome) — Evolved genomes can seed constraint parameters
- [**creative-engine-c**](https://github.com/SuperInstance/creative-engine-c) — Chaotic dynamics for generative material
- [**flux-hyperbolic**](https://github.com/SuperInstance/flux-hyperbolic) — Tradition embeddings for context-aware constraints

## License

MIT
