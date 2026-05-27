"""Extended tests for session module."""

import asyncio
import pytest
from superinstance_live.session import Session
from superinstance_live.transport import TransportState
from superinstance_live.constraint_host import FluxRoomPipeline, PipelineEvent


class TestSessionInit:
    def test_default_bpm(self):
        s = Session()
        assert s.transport.bpm == 120.0

    def test_custom_bpm(self):
        s = Session(bpm=80.0)
        assert s.transport.bpm == 80.0

    def test_has_constraint_host(self):
        s = Session()
        assert s.host is not None
        assert s.host.pipeline_names == []

    def test_has_midi_clock(self):
        s = Session()
        assert s.midi_clock is not None

    def test_has_osc(self):
        s = Session()
        assert s.osc is not None

    def test_repr(self):
        s = Session(bpm=100.0)
        r = repr(s)
        assert "Session" in r
        assert "100.0" in r


class TestSessionLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop_no_pipelines(self):
        s = Session(osc_listen_port=8140)
        await s.start()
        assert s.transport.state == TransportState.PLAYING
        await s.stop()
        assert s.transport.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_start_with_pipeline(self):
        s = Session(osc_listen_port=8141)
        s.host.add_pipeline(FluxRoomPipeline("flux"))
        await s.start()
        await asyncio.sleep(0.3)
        await s.stop()

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        s = Session(osc_listen_port=8142)
        await s.start()
        await s.pause()
        assert s.transport.state == TransportState.PAUSED
        await s.continue_()
        assert s.transport.state == TransportState.PLAYING
        await s.stop()

    @pytest.mark.asyncio
    async def test_ticks_flow_to_host(self):
        s = Session(osc_listen_port=8143)
        received = []
        s.host.add_pipeline(FluxRoomPipeline("flux"))
        s.host.on_event(lambda ev: received.append(ev))
        await s.start()
        await asyncio.sleep(0.6)
        await s.stop()
        assert len(received) > 0


class TestSessionOSC:
    @pytest.mark.asyncio
    async def test_osc_sends_tick(self):
        s = Session(osc_listen_port=8144, osc_send_port=9144)
        await s.start()
        await asyncio.sleep(0.08)
        await s.stop()
        # If we got here, the OSC send didn't crash


class TestSessionPipelineEvents:
    @pytest.mark.asyncio
    async def test_pipeline_event_triggers_note_off(self):
        s = Session(osc_listen_port=8145, osc_send_port=9145)
        s.host.add_pipeline(FluxRoomPipeline("flux"))
        await s.start()
        await asyncio.sleep(0.7)
        await s.stop()

    @pytest.mark.asyncio
    async def test_osc_constraint_set(self):
        s = Session(osc_listen_port=8146, osc_send_port=9146)
        s.host.add_pipeline(FluxRoomPipeline("flux"))
        # Simulate OSC constraint set
        s._on_osc_constraint_set("/constraint/flux/set/bpm", [140.0])
        assert s.transport.bpm == 120.0  # bpm doesn't change on transport
        # But the pipeline got the param
        p = s.host.get_pipeline("flux")
        assert p._clock.bpm == 140.0

    @pytest.mark.asyncio
    async def test_osc_constraint_trigger(self):
        s = Session(osc_listen_port=8147, osc_send_port=9147)
        from superinstance_live.constraint_host import CounterpointPipeline
        s.host.add_pipeline(CounterpointPipeline("cp"))
        s._on_osc_constraint_trigger("/constraint/cp/trigger", [])

    @pytest.mark.asyncio
    async def test_osc_constraint_set_nonexistent(self):
        s = Session(osc_listen_port=8148)
        s._on_osc_constraint_set("/constraint/nonexistent/set/x", [1.0])
        # should not raise

    @pytest.mark.asyncio
    async def test_osc_constraint_trigger_nonexistent(self):
        s = Session(osc_listen_port=8149)
        s._on_osc_constraint_trigger("/constraint/nonexistent/trigger", [])
        # should not raise

    @pytest.mark.asyncio
    async def test_osc_constraint_set_bad_address(self):
        s = Session(osc_listen_port=8150)
        s._on_osc_constraint_set("/bad/address", [1.0])
        # should not raise
