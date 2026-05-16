"""In-process pub/sub for WebSocket alerts."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AlertHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._clients:
            return
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception as exc:  # pragma: no cover - network blips
                logger.warning("alert broadcast failed: %s", exc)
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._main_loop = loop

    def broadcast_threadsafe(self, message: dict[str, Any]) -> None:
        """Send from any thread; safely no-ops when no event loop is running."""
        loop = getattr(self, "_main_loop", None)
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)


alert_hub = AlertHub()
