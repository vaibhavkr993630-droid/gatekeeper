"""In-process fan-out of gateway events to dashboard WebSockets.

`{tenant_id: {sockets}}`. Isolation is structural: `publish(tenant_id, ...)` can
only ever reach sockets registered under that same tenant, and a socket's tenant
is taken from its verified JWT at connect time — never from anything the client says.

Single-process only. At scale each gateway node would publish to Redis pub/sub (or
a message bus) and each dashboard node would subscribe; see `app/ws/README.md`.
"""
import asyncio
import logging
from collections import defaultdict

from starlette.websockets import WebSocket

log = logging.getLogger("gatekeeper.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._by_tenant: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def register(self, tenant_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_tenant[tenant_id].add(ws)

    async def unregister(self, tenant_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_tenant.get(tenant_id, set()).discard(ws)
            if not self._by_tenant.get(tenant_id):
                self._by_tenant.pop(tenant_id, None)

    def connection_count(self, tenant_id: int) -> int:
        return len(self._by_tenant.get(tenant_id, ()))

    async def publish(self, tenant_id: int, message: dict) -> None:
        targets = list(self._by_tenant.get(tenant_id, ()))
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — a broken socket must not block the others
                log.debug("dropping dead websocket for tenant %s", tenant_id)
                await self.unregister(tenant_id, ws)


manager = ConnectionManager()
