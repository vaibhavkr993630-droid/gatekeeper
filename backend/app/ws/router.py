"""Dashboard live-feed WebSocket.

    ws://<host>/ws/feed?token=<tenant JWT>

The tenant is resolved from the verified token; the socket only ever receives
events for that tenant's services. Clients cannot subscribe to anything else —
there is no subscribe message.
"""
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import JWTError, decode_access_token
from app.crud import request_log as crud_log
from app.crud import tenant as crud_tenant
from app.db.session import SessionLocal
from app.models.tenant import TenantUser
from app.ws.events import event_from_log
from app.ws.manager import manager

log = logging.getLogger("gatekeeper.ws")

router = APIRouter()

# close codes (4000-4999 is the app-private range)
_WS_UNAUTHORIZED = 4401

_SNAPSHOT_SIZE = 50


async def _authenticate(token: str) -> TenantUser | None:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
    async with SessionLocal() as db:
        user = await crud_tenant.get_user(db, user_id)
        return user if (user and user.is_active) else None


@router.websocket("/feed")
async def feed(ws: WebSocket, token: str = Query(...)) -> None:
    user = await _authenticate(token)
    if user is None:
        await ws.close(code=_WS_UNAUTHORIZED)
        return

    tenant_id = user.tenant_id
    await ws.accept()

    async with SessionLocal() as db:
        recent = await crud_log.recent_for_tenant(db, tenant_id, limit=_SNAPSHOT_SIZE)
    await ws.send_json(
        {
            "type": "snapshot",
            "events": [event_from_log(row, name) for row, name in reversed(recent)],
        }
    )

    await manager.register(tenant_id, ws)
    try:
        while True:
            # we only push; reading is how we notice the client went away
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unregister(tenant_id, ws)
