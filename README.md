# superinstance-live

DAW-agnostic session controller for SuperInstance constraint music systems.

Orchestrates **flux-tensor-midi**, **groove-analyzer**, and **counterpoint-engine** in real time via **OSC + MIDI Clock**.

## Install

```bash
pip install -e .
```

## Quick start

```bash
superinstance-live start --bpm 120 --port 8000
```

## Architecture

| Module | Role |
|--------|------|
| `session.py` | Holds state for running compositions |
| `transport.py` | Single source of truth for time (play/stop/pause, BPM, time signature) |
| `midi_clock.py` | MIDI Clock generator (24 PPQN) via `mido` |
| `osc_bridge.py` | OSC server/client for DAW communication |
| `constraint_host.py` | Loads constraint pipelines, feeds them transport state |
| `cli.py` | Entry point: `superinstance-live start --bpm 120 --port 8000` |

## OSC API

| Address | Args | Description |
|---------|------|-------------|
| `/transport/play` | — | Start playback |
| `/transport/stop` | — | Stop playback |
| `/transport/pause` | — | Pause playback |
| `/transport/bpm` | `f` | Set BPM |
| `/constraint/{name}/set/{param}` | `f` | Set pipeline parameter |
| `/constraint/{name}/trigger` | — | Trigger pipeline regeneration |

## Design

- Everything is **async** (`asyncio`).
- **Transport** is the single source of truth for time.
- **Constraint host** receives tick events and produces MIDI events.
- **Ableton Link** compatibility is the goal but not required for v0.1.
