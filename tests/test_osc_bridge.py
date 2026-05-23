"""Tests for osc_bridge module."""

import asyncio
import pytest
from superinstance_live.osc_bridge import OSCBridge


class TestOSCBridge:
    def test_init(self):
        bridge = OSCBridge(listen_port=8123, send_port=9123)
        assert bridge.listen_port == 8123
        assert bridge.send_port == 9123

    def test_register_handler(self):
        bridge = OSCBridge()
        called = []
        bridge.register("/test", lambda a, args: called.append(args))
        bridge._emit("/test", [1.0])
        assert called == [[1.0]]

    def test_unregister_handler(self):
        bridge = OSCBridge()
        called = []
        def h(a, args):
            called.append(args)
        bridge.register("/test", h)
        bridge.unregister("/test", h)
        bridge._emit("/test", [1.0])
        assert called == []

    def test_transport_play_handler(self):
        bridge = OSCBridge()
        called = []
        bridge.register("/transport/play", lambda a, args: called.append(True))
        bridge._on_play("/transport/play")
        assert called

    def test_transport_stop_handler(self):
        bridge = OSCBridge()
        called = []
        bridge.register("/transport/stop", lambda a, args: called.append(True))
        bridge._on_stop("/transport/stop")
        assert called

    def test_transport_bpm_handler(self):
        bridge = OSCBridge()
        called = []
        bridge.register("/transport/bpm", lambda a, args: called.append(args))
        bridge._on_bpm("/transport/bpm", 140.0)
        assert called[0] == [140.0]

    def test_constraint_set_handler(self):
        bridge = OSCBridge()
        called = []
        bridge.register("/constraint/cp/set/species", lambda a, args: called.append(args))
        bridge._on_constraint_set("/constraint/cp/set/species", 2.0)
        assert called[0] == [2.0]

    @pytest.mark.asyncio
    async def test_start_stop(self):
        bridge = OSCBridge(listen_port=8124, send_port=9124)
        await bridge.start()
        assert bridge._transport is not None
        await bridge.stop()
        assert bridge._transport is None
