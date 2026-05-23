"""CLI: superinstance-live start --bpm 120 --port 8000"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from .session import Session
from .constraint_host import FluxRoomPipeline, CounterpointPipeline, GroovePipeline
from counterpoint_engine.generator import Species, Scale, VoiceRange
from groove_analyzer.microtiming import GrooveTiming, TrackTiming, OnsetEvent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="superinstance-live",
        description="DAW-agnostic session controller for constraint music systems.",
    )
    sub = parser.add_subparsers(dest="command")
    start = sub.add_parser("start", help="Start a live session")
    start.add_argument("--bpm", type=float, default=120.0, help="Initial BPM")
    start.add_argument("--port", type=int, default=8000, help="OSC listen port")
    start.add_argument("--send-port", type=int, default=9000, help="OSC send port")
    start.add_argument("--midi-port", type=str, default=None, help="MIDI output port name")
    start.add_argument("--counterpoint", action="store_true", help="Enable counterpoint pipeline")
    start.add_argument("--groove", action="store_true", help="Enable groove pipeline")
    start.add_argument("--flux", action="store_true", default=True, help="Enable flux pipeline (default)")
    return parser


async def _run_session(args) -> None:
    session = Session(
        bpm=args.bpm,
        osc_listen_port=args.port,
        osc_send_port=args.send_port,
        midi_port=args.midi_port,
    )

    if args.flux:
        session.host.add_pipeline(FluxRoomPipeline("flux"))

    if args.counterpoint:
        session.host.add_pipeline(
            CounterpointPipeline(
                "counterpoint",
                cantus_firmus=[60, 62, 64, 65, 64, 62, 60],
                species=Species.FIRST,
                scale=Scale(),
                voice_range=VoiceRange(),
            )
        )

    if args.groove:
        # Build a dummy groove timing
        onsets = [OnsetEvent(beat=i, deviation_ms=0.0) for i in range(8)]
        track = TrackTiming(track_name="drums", onsets=onsets)
        timing = GrooveTiming(tracks=[track])
        session.host.add_pipeline(GroovePipeline("groove", timing=timing))

    print(f"[superinstance-live] Starting session: {session}")
    print(f"[superinstance-live] OSC listen on port {args.port}")
    print(f"[superinstance-live] Press Ctrl+C to stop")

    await session.start()

    stop_event = asyncio.Event()

    def _on_signal(sig, frame) -> None:
        print(f"\n[superinstance-live] Received signal {sig}, stopping...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    await session.stop()
    print("[superinstance-live] Session stopped.")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "start":
        asyncio.run(_run_session(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
