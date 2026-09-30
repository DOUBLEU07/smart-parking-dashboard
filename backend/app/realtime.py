"""In-process WebSocket fan-out.

Runs inside the single backend process (uvicorn with one worker). Scaling to
several workers would need a shared broker such as Redis pub/sub or Postgres
LISTEN/NOTIFY.
"""

import asyncio
import json
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)

    async def broadcast(self, message: dict) -> None:
        data = json.dumps(message, default=str, ensure_ascii=False)
        async with self._lock:
            clients = list(self._clients)
        dead = []
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001 - a broken socket must not stop the fan-out
                dead.append(ws)
        for ws in dead:
            await self.remove(ws)
        log.debug("broadcast %s to %d clients", message.get("type"), len(clients) - len(dead))


manager = ConnectionManager()


def parking_event(reason: str, **details) -> dict:
    return {"type": "parking.updated", "reason": reason, **details}
