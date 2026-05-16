"""WebSocket endpoint for live alerts."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.alerts import alert_hub

router = APIRouter(tags=["alerts"])


@router.websocket("/ws/alerts")
async def alerts_ws(ws: WebSocket) -> None:
    await alert_hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        alert_hub.disconnect(ws)
