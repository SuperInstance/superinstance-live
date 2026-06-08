# INTEGRATION.md — superinstance-live

## Role in the SuperInstance Ecosystem

superinstance-live is the **DAW-agnostic session controller** that orchestrates constraint music systems in real time. It bridges the gap between SuperInstance's agent/creative layers and actual performance by providing MIDI Clock, OSC, transport control, and a constraint pipeline host that runs `flux-tensor-midi`, `counterpoint-engine`, and `groove-analyzer` inside a unified session.

## SuperInstance Integration Points

### 1. flux-hyperbolic-rs — Tradition-Driven Room Initialization
- `FluxRoomPipeline` queries `TraditionEmbedding::standard_traditions()` to set initial dial positions
- `set_param("tradition", "Jazz")` remaps the room's hyperbolic embedding and updates rhythmic roles
- `on_tick()` reads the current tradition's dial triplet and modulates `RoomMusician` parameters

### 2. creative-engine-rust — Real-Time Creative Dynamics
- Each `FluxRoomPipeline` hosts a `CreativeSystem` whose `step()` is called on transport ticks
- `set_param("epsilon", value)` adjusts `CreativeThermostat` target diversity
- `trigger()` injects a perturbation into the Lorenz system (e.g., on beat 1 of every 4 bars)
- `PipelineEvent.meta` carries `quality()` metrics back to OSC `/creative/quality`

### 3. constraint-dsl — Declarative Pipeline Definitions
- `ConstraintHost.add_pipeline()` accepts pipelines defined in constraint-dsl YAML
- The DSL is compiled once at session start; `on_tick()` executes the compiled graph
- Example: a counterpoint pipeline declares voice-leading constraints; `on_tick()` resolves them against current transport state
- `set_param` mutations feed into `Runtime.execute(inputs)`

### 4. constraint-dynamics-rs — Real-Time Constraint Solving
- Inside `CounterpointPipeline.on_tick()`, a `Solver` resolves voice-leading constraints
- `EnergyLandscape.relaxed_solve()` handles over-constrained ticks gracefully (drops lowest-strength constraints)
- Solver timeout is set to `< tick_duration` to prevent transport jitter

### 5. si-runtime-python — Fleet Orchestration
- `Fleet` (si-runtime-python) can spawn `superinstance-live` sessions as subprocesses
- `Fleet.spectral_rank()` ranks live sessions by their cumulative `PipelineEvent` quality scores
- `Fleet.conservation_audit()` checks that each session's creative energy expenditure stays within its `AgentBudget`

### 6. si-cli — Session Lifecycle Management
- `si-cli scan` discovers `superinstance-live` sessions by finding `Session` class usage
- `si-cli check` validates that all referenced MIDI ports, OSC ports, and pipeline YAML files are accessible
- `si-cli audit` logs session duration, BPM stability, and constraint violation counts to Supabase `fleet_events`

### 7. plato-adapters — Adapter-Driven I/O
- `OSCBridge` receives `/constraint/{name}/set/{param} f` messages
- `plato-adapters` transforms raw OSC args into typed pipeline inputs
- `AdapterRegistry.chain(["osc_parse", "normalize", "pipeline_input"])` bridges external DAWs to internal constraint graphs

## Dial / Room / Snap Compatibility

| Primitive | Mapping |
|-----------|---------|
| **Dial**  | `Transport.bpm` and pipeline `set_param` calls; dial position = param value normalized to [0, 1] |
| **Room**  | Each `FluxRoomPipeline` / `CounterpointPipeline` / `GroovePipeline` is a Room; `Session` is the fleet |
| **Snap**  | `Session.snap()` freezes all pipelines at current state, disables adaptation, outputs looped pattern |
| **Cascade**| Transport ticks cascade from `Session` → `ConstraintHost` → all active pipelines; child rooms inherit parent BPM and time signature |

## Energy Conservation

superinstance-live enforces conservation at the session level:
- Each pipeline has a `budget` field (default drawn from `AgentBudget`)
- `ConstraintHost.on_tick()` tracks cumulative computational cost:
  - Solver iterations → η
  - Creative system steps → γ
  - MIDI/OSC I/O → negligible (accounted in overhead)
- If a tick exceeds budget, the host drops lowest-priority pipelines until cost fits

## Quick Start

```bash
# Start a session with Jazz room at 120 BPM
superinstance-live start --bpm 120 --port 8000 --flux

# Send OSC from another process to change tradition
oscsend localhost 8000 /constraint/flux/set/tradition s "Blues"
```

Python:
```python
from superinstance_live import Session, FluxRoomPipeline

session = Session(bpm=120)
session.host.add_pipeline(FluxRoomPipeline("room1", tradition="Jazz"))
asyncio.run(session.start())
```

## Tests

```bash
pytest tests/
```

Transport timing, OSC round-trip, MIDI clock stability, and constraint host tick latency tests must pass.
