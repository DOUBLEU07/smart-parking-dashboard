import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..database import SessionLocal
from ..models import User
from ..realtime import manager
from ..security import decode_token

router = APIRouter()
log = logging.getLogger(__name__)

AUTH_TIMEOUT_SECONDS = 5


def _authenticate(token: str) -> User | None:
    user_id = decode_token(token)
    if user_id is None:
        return None
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return user if user and user.is_active else None


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Clients authenticate with their first message: {"type": "auth", "token": "..."}.

    The token is kept out of the URL so it never lands in proxy access logs.
    """
    await ws.accept()
    try:
        raw = await asyncio.wait_for(ws.receive_text(), AUTH_TIMEOUT_SECONDS)
        msg = json.loads(raw)
        user = await asyncio.to_thread(_authenticate, str(msg.get("token", ""))) if msg.get("type") == "auth" else None
    except (TimeoutError, json.JSONDecodeError, WebSocketDisconnect, AttributeError):
        user = None
    if user is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.add(ws)
    await ws.send_json({"type": "ready"})
    log.info("ws connected user=%s (clients=%d)", user.username, manager.count)
    try:
        while True:
            text = await ws.receive_text()
            if text == "ping" or '"ping"' in text:
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.remove(ws)
        log.info("ws disconnected user=%s (clients=%d)", user.username, manager.count)
