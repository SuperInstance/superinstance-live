"""
superinstance-live — DAW-agnostic session controller.

Orchestrates constraint music systems (flux-tensor-midi, groove-analyzer,
counterpoint-engine) in real time via OSC + MIDI Clock.
"""

__version__ = "0.1.0"

from .session import Session
from .transport import Transport, TransportState
from .constraint_host import ConstraintHost
from .midi_clock import MidiClockOut
from .osc_bridge import OSCBridge

__all__ = [
    "Session",
    "Transport",
    "TransportState",
    "ConstraintHost",
    "MidiClockOut",
    "OSCBridge",
    "__version__",
]
