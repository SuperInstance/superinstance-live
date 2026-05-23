"""Tests for session module."""

import asyncio
import pytest
from superinstance_live.session import Session
from superinstance_live.transport import TransportState
from superinstance_live.constraint_host import FluxRoomPipeline


class TestSession:
    def test_init(self):
        session = Session(bpm=130.0, osc_listen_port=8125)
        assert session.transport.bpm == 130.0
        assert session.transport.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_start_stop(self):
        session = Session(bpm=120.0, osc_listen_port=8126)
        session.host.add_pipeline(FluxRoomPipeline("flux1"))
        await session.start()
        assert session.transport.state == TransportState.PLAYING
        await session.stop()
        assert session.transport.state == TransportState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_continue(self):
        session = Session(bpm=120.0, osc_listen_port=8127)
        await session.start()
        await session.pause()
        assert session.transport.state == TransportState.PAUSED
        await session.continue_()
        assert session.transport.state == TransportState.PLAYING
        await session.stop()

    def test_add_pipeline_and_play(self):
        session = Session()
        pipe = FluxRoomPipeline("test")
        session.host.add_pipeline(pipe)
        assert "test" in session.host.pipeline_names
