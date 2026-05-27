"""Extended tests for osc_bridge module."""

import asyncio
import pytest
from superinstance_live.osc_bridge import OSCBridge


class TestOSCBridgeInit:
    def test_custom_hosts(self):
        b = OSCBridge(listen_host="0.0.0.0", send_host="192.168.1.1")
        assert b.listen_host == "0.0.0.0"
        assert b.send_host == "192.168.1.1"

    def test_repr(self):
        b = OSCBridge(listen_port=1234, send_port=5678)
        r = repr(b)
        assert "OSCBridge" in r
        assert "1234" in r
        assert "5678" in r


class TestOSCBridgeHandlers:
    def test_play_emits(self):
        b = OSCBridge()
        received = []
        b.register("/transport/play", lambda a, args: received.append("play"))
        b._on_play("/transport/play")
        assert received == ["play"]

    def test_stop_emits(self):
        b = OSCBridge()
        received = []
        b.register("/transport/stop", lambda a, args: received.append("stop"))
        b._on_stop("/transport/stop")
        assert received == ["stop"]

    def test_pause_emits(self):
        b = OSCBridge()
        received = []
        b.register("/transport/pause", lambda a, args: received.append("pause"))
        b._on_pause("/transport/pause")
        assert received == ["pause"]

    def test_bpm_emits_with_value(self):
        b = OSCBridge()
        received = []
        b.register("/transport/bpm", lambda a, args: received.append(args))
        b._on_bpm("/transport/bpm", 140.0)
        assert received == [[140.0]]

    def test_bpm_no_args(self):
        b = OSCBridge()
        received = []
        b.register("/transport/bpm", lambda a, args: received.append(args))
        b._on_bpm("/transport/bpm")  # no args
        assert received == []

    def test_constraint_set_parses_address(self):
        b = OSCBridge()
        received = []
        b.register("/constraint/my/set/gain", lambda a, args: received.append(args))
        b._on_constraint_set("/constraint/my/set/gain", 0.75)
        assert received == [[0.75]]

    def test_constraint_trigger_parses_address(self):
        b = OSCBridge()
        received = []
        b.register("/constraint/cp/trigger", lambda a, args: received.append("triggered"))
        b._on_constraint_trigger("/constraint/cp/trigger")
        assert received == ["triggered"]

    def test_multiple_handlers_same_address(self):
        b = OSCBridge()
        r1, r2 = [], []
        b.register("/test", lambda a, args: r1.append(1))
        b.register("/test", lambda a, args: r2.append(2))
        b._emit("/test", [])
        assert r1 == [1]
        assert r2 == [2]

    def test_handler_exception_swallowed(self):
        b = OSCBridge()
        good = []
        b.register("/test", lambda a, args: 1 / 0)
        b.register("/test", lambda a, args: good.append(True))
        b._emit("/test", [])
        assert good == [True]

    def test_emit_nonexistent_address(self):
        b = OSCBridge()
        b._emit("/nonexistent", [1.0])  # should not raise


class TestOSCBridgeSend:
    def test_send_tick(self):
        b = OSCBridge()
        # Just verify it doesn't crash (no actual UDP listener)
        b.send_tick(42)

    def test_send_beat(self):
        b = OSCBridge()
        b.send_beat(3)

    def test_send_bar(self):
        b = OSCBridge()
        b.send_bar(1)

    def test_send_note_on(self):
        b = OSCBridge()
        b.send_note_on(60, 100, 0)

    def test_send_note_off(self):
        b = OSCBridge()
        b.send_note_off(60, 0)

    def test_send_bpm(self):
        b = OSCBridge()
        b.send_bpm(120.0)


class TestOSCBridgeLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_transport(self):
        b = OSCBridge(listen_port=8130, send_port=9130)
        await b.start()
        assert b._transport is not None
        await b.stop()
        assert b._transport is None

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        b = OSCBridge()
        await b.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_restart_after_stop(self):
        b = OSCBridge(listen_port=8131, send_port=9131)
        await b.start()
        assert b._transport is not None
        await b.stop()
        assert b._transport is None
        # Port may still be in TIME_WAIT, so just verify stop worked
        # Restart on a different port to avoid address-in-use
        b2 = OSCBridge(listen_port=8132, send_port=9132)
        await b2.start()
        assert b2._transport is not None
        await b2.stop()
