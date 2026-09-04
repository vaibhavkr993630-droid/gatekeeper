"""Push a just-handled gateway request to the tenant's dashboard sockets.

Runs as a BackgroundTask, independent of the RequestLog write — either can fail
without affecting the other, and neither is on the request's hot path.
"""
import logging

from app.gateway.recorder import RequestRecord
from app.ws.events import request_event
from app.ws.manager import manager

log = logging.getLogger("gatekeeper.ws")


async def broadcast_request(rec: RequestRecord) -> None:
    if manager.connection_count(rec.tenant_id) == 0:
        return
    try:
        await manager.publish(
            rec.tenant_id,
            request_event(
                service_id=rec.service_id,
                service_name=rec.service_name,
                allowed=rec.allowed,
                status_code=rec.status_code,
                method=rec.method,
                path=rec.path,
                client_ip=rec.client_ip,
                rule_algorithm=rec.rule_algorithm,
                latency_ms=rec.latency_ms,
            ),
        )
    except Exception:
        log.exception("failed to broadcast gateway request")
