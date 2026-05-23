"""Tests for transport module."""

import asyncio
import pytest
from superinstance_live.transport import Transport, TransportState, TimeSignature


@pytest.fixture
def transport():
    return Transport(bpm=120.0)


class TestTransport:
    def test_init_defaults(self, transport):
        assert transport.bpm == 120.0
        assert transport.state == TransportState.STOPPED
        assert transport.tick_count == 0
        assert transport.beat_count == 0
        assert transport.bar_count == 0

    def test_pulse_interval(self, transport):
        # 120 BPM -> 60/(120*24) = 0.020833... s per tick
        assert transport.pulse_interval_s() == pytest.approx(0.020833, rel=1e-3)

    def test_beat_duration(self, transport):
        assert transport.beat_duration_s() == pytest.approx(0.5, rel=1e-9)

    def test_bpm_validation(self):
        with pytest.raises(ValueError):
            Transport(bpm=0)
        with pytest.raises(ValueError):
            Transport(bpm=-10)

    def test_bpm_setter(self, transport):
        transport.bpm = 140.0
        assert transport.bpm == 140.0
        with pytest.raises(ValueError):
            transport.bpm = 0

    @pytest.mark.asyncio
    async def test_start_stop(self, transport):
        await transport.start()
        assert transport.state == TransportState.PLAYING
        await transport.stop()
        assert transport.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_continue(self, transport):
        await transport.start()
        assert transport.state == TransportState.PLAYING
        await transport.pause()
        assert transport.state == TransportState.PAUSED
        await transport.continue_()
        assert transport.state == TransportState.PLAYING
        await transport.stop()

    @pytest.mark.asyncio
    async def test_tick_callbacks(self, transport):
        ticks = []
        transport.on_tick(lambda t, n: ticks.append(t))
        await transport.start()
        await asyncio.sleep(0.12)  # ~6 ticks at 120 BPM
        await transport.stop()
        assert len(ticks) >= 4

    @pytest.mark.asyncio
    async def test_beat_callback(self, transport):
        beats = []
        transport.on_beat(lambda b, n: beats.append(b))
        await transport.start()
        await asyncio.sleep(0.55)  # slightly more than 1 beat
        await transport.stop()
        assert len(beats) >= 1

    @pytest.mark.asyncio
    async def test_bar_callback(self, transport):
        bars = []
        transport.on_bar(lambda b, n: bars.append(b))
        ts = TimeSignature(numerator=2)
        transport.time_signature = ts
        await transport.start()
        await asyncio.sleep(1.1)  # slightly more than 2 beats at 2/4
        await transport.stop()
        assert len(bars) >= 1

    def test_time_signature_validation(self):
        with pytest.raises(ValueError):
            TimeSignature(numerator=0)
        with pytest.raises(ValueError):
            TimeSignature(denominator=0)

    def test_reset(self, transport):
        transport.reset()
        assert transport.tick_count == 0
        assert transport.beat_count == 0

    def test_remove_callback(self, transport):
        def cb(t, n):
            pass
        transport.on_tick(cb)
        transport.remove_tick_callback(cb)
        # Should not raise
