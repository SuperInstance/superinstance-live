"""Extended tests for transport module — edge cases, repr, concurrency."""

import asyncio
import pytest
from superinstance_live.transport import Transport, TransportState, TimeSignature


class TestTimeSignature:
    def test_defaults(self):
        ts = TimeSignature()
        assert ts.numerator == 4
        assert ts.denominator == 4
        assert ts.beats_per_bar() == 4

    def test_custom(self):
        ts = TimeSignature(numerator=7, denominator=8)
        assert ts.beats_per_bar() == 7

    def test_numerator_one(self):
        ts = TimeSignature(numerator=1)
        assert ts.beats_per_bar() == 1

    def test_invalid_numerator_negative(self):
        with pytest.raises(ValueError):
            TimeSignature(numerator=-1)

    def test_invalid_denominator_negative(self):
        with pytest.raises(ValueError):
            TimeSignature(denominator=-2)

    def test_large_values(self):
        ts = TimeSignature(numerator=15, denominator=16)
        assert ts.beats_per_bar() == 15


class TestTransportInit:
    def test_default_bpm(self):
        t = Transport()
        assert t.bpm == 120.0

    def test_custom_bpm(self):
        t = Transport(bpm=200.0)
        assert t.bpm == 200.0

    def test_bpm_boundary(self):
        t = Transport(bpm=0.001)
        assert t.bpm == 0.001

    def test_default_time_signature(self):
        t = Transport()
        assert t.time_signature.numerator == 4

    def test_custom_time_signature(self):
        ts = TimeSignature(3, 4)
        t = Transport(time_signature=ts)
        assert t.time_signature.numerator == 3


class TestTransportTiming:
    def test_pulse_interval_60bpm(self):
        t = Transport(bpm=60.0)
        # 60/(60*24) = 1/24 ≈ 0.04167
        assert t.pulse_interval_s() == pytest.approx(1.0 / 24.0, rel=1e-6)

    def test_pulse_interval_240bpm(self):
        t = Transport(bpm=240.0)
        # 60/(240*24) = 60/5760 ≈ 0.01042
        assert t.pulse_interval_s() == pytest.approx(60.0 / 5760.0, rel=1e-6)

    def test_beat_duration_60bpm(self):
        t = Transport(bpm=60.0)
        assert t.beat_duration_s() == pytest.approx(1.0)

    def test_beat_duration_180bpm(self):
        t = Transport(bpm=180.0)
        assert t.beat_duration_s() == pytest.approx(1.0 / 3.0, rel=1e-6)


class TestTransportControl:
    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        t = Transport(bpm=120.0)
        await t.start()
        assert t.state == TransportState.PLAYING
        await t.start()  # no-op
        assert t.state == TransportState.PLAYING
        await t.stop()

    @pytest.mark.asyncio
    async def test_pause_when_stopped_is_noop(self):
        t = Transport(bpm=120.0)
        await t.pause()
        assert t.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_continue_when_playing_is_noop(self):
        t = Transport(bpm=120.0)
        await t.start()
        await t.continue_()
        assert t.state == TransportState.PLAYING
        await t.stop()

    @pytest.mark.asyncio
    async def test_continue_when_stopped_is_noop(self):
        t = Transport(bpm=120.0)
        await t.continue_()
        assert t.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_resets_to_stopped(self):
        t = Transport(bpm=120.0)
        await t.start()
        await t.stop()
        assert t.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_start_after_stop_resets_counters(self):
        t = Transport(bpm=120.0)
        await t.start()
        await asyncio.sleep(0.1)
        await t.stop()
        assert t.tick_count > 0
        await t.start()
        assert t.tick_count == 0
        assert t.beat_count == 0
        assert t.bar_count == 0
        await t.stop()


class TestTransportCallbacks:
    @pytest.mark.asyncio
    async def test_tick_callback_exception_is_swallowed(self):
        t = Transport(bpm=120.0)
        errors = []

        def bad_cb(tick, now):
            raise RuntimeError("boom")

        def good_cb(tick, now):
            errors.append(tick)

        t.on_tick(bad_cb)
        t.on_tick(good_cb)
        await t.start()
        await asyncio.sleep(0.08)
        await t.stop()
        assert len(errors) > 0  # good_cb still gets called

    @pytest.mark.asyncio
    async def test_beat_callback_exception_swallowed(self):
        t = Transport(bpm=120.0)
        beats = []

        def bad(b, now):
            raise RuntimeError("beat boom")

        def good(b, now):
            beats.append(b)

        t.on_beat(bad)
        t.on_beat(good)
        await t.start()
        await asyncio.sleep(0.6)
        await t.stop()
        assert len(beats) > 0

    @pytest.mark.asyncio
    async def test_bar_callback_exception_swallowed(self):
        t = Transport(bpm=240.0)  # fast for testing
        bars = []

        def bad(b, now):
            raise RuntimeError("bar boom")

        def good(b, now):
            bars.append(b)

        t.on_bar(bad)
        t.on_bar(good)
        await t.start()
        await asyncio.sleep(1.5)
        await t.stop()
        assert len(bars) > 0

    @pytest.mark.asyncio
    async def test_multiple_tick_callbacks(self):
        t = Transport(bpm=120.0)
        a, b = [], []
        t.on_tick(lambda tick, now: a.append(tick))
        t.on_tick(lambda tick, now: b.append(tick))
        await t.start()
        await asyncio.sleep(0.08)
        await t.stop()
        assert len(a) > 0
        assert a == b

    def test_remove_nonexistent_callback(self):
        t = Transport(bpm=120.0)
        t.remove_tick_callback(lambda t, n: None)  # should not raise


class TestTransportRepr:
    def test_repr_stopped(self):
        t = Transport(bpm=100.0)
        r = repr(t)
        assert "Transport" in r
        assert "100.0" in r
        assert "STOPPED" in r

    @pytest.mark.asyncio
    async def test_repr_playing(self):
        t = Transport(bpm=100.0)
        await t.start()
        r = repr(t)
        assert "PLAYING" in r
        await t.stop()


class TestTransportTimeSignatureChange:
    @pytest.mark.asyncio
    async def test_change_ts_while_playing(self):
        t = Transport(bpm=120.0)
        bars = []
        t.on_bar(lambda b, now: bars.append(b))
        await t.start()
        await asyncio.sleep(0.3)
        t.time_signature = TimeSignature(2, 4)
        await asyncio.sleep(1.0)
        await t.stop()
        # Should have some bars
        assert len(bars) > 0


class TestTransportReset:
    @pytest.mark.asyncio
    async def test_reset_while_stopped(self):
        t = Transport(bpm=120.0)
        await t.start()
        await asyncio.sleep(0.1)
        await t.stop()
        assert t.tick_count > 0
        t.reset()
        assert t.tick_count == 0
        assert t.beat_count == 0
        assert t.bar_count == 0

    @pytest.mark.asyncio
    async def test_reset_does_not_clear_while_playing(self):
        """Reset only clears counters; it doesn't stop the transport."""
        t = Transport(bpm=120.0)
        await t.start()
        await asyncio.sleep(0.05)
        old_ticks = t.tick_count
        t.reset()  # manual reset
        assert t.tick_count == 0  # reset clears
        await t.stop()
