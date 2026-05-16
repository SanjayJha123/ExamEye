"""Phase 6: WebSocket live alerts."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from examye.services.alerts import alert_hub


def test_websocket_connect_and_disconnect(isolated_examye):
    client = TestClient(isolated_examye["app"])
    assert alert_hub.connection_count == 0
    with client.websocket_connect("/ws/alerts") as ws:
        assert alert_hub.connection_count == 1
        # Round-trip: server-side broadcast should reach us.
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                alert_hub.broadcast({"type": "event", "kind": "phone_visible", "severity": "high"})
            )
        finally:
            loop.close()

        raw = ws.receive_text()
        payload = json.loads(raw)
        assert payload["type"] == "event"
        assert payload["kind"] == "phone_visible"

    assert alert_hub.connection_count == 0


def test_alerts_page_renders(isolated_examye):
    client = TestClient(isolated_examye["app"])
    r = client.get("/alerts")
    assert r.status_code == 200
    assert "Live alerts" in r.text


def test_threadsafe_broadcast_noop_without_loop(isolated_examye):
    # Without a running event loop and no connected clients, must not raise.
    alert_hub.broadcast_threadsafe({"type": "event", "severity": "medium"})
