"""Off-hot-path persistence: RequestLog insert + API-key touch.

Runs as a FastAPI BackgroundTask after the response has been sent, so the client
never waits on these writes. Opens its own DB session — the request-scoped one is
already closed by the time this runs.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import func, update

from app.db.session import SessionLocal
from app.models.request_log import RequestLog
from app.models.service import ApiKey

log = logging.getLogger("gatekeeper.gateway")


@dataclass(frozen=True, slots=True)
class RequestRecord:
    tenant_id: int
    service_id: int
    service_name: str
    api_key_id: int
    allowed: bool
    status_code: int
    method: str
    path: str
    client_ip: str
    rule_algorithm: str | None
    latency_ms: int | None


async def record_request(rec: RequestRecord) -> None:
    try:
        async with SessionLocal() as db:
            db.add(
                RequestLog(
                    tenant_id=rec.tenant_id,
                    service_id=rec.service_id,
                    allowed=rec.allowed,
                    status_code=rec.status_code,
                    method=rec.method,
                    path=rec.path[:2048],
                    client_ip=rec.client_ip[:64],
                    rule_algorithm=rec.rule_algorithm,
                    latency_ms=rec.latency_ms,
                )
            )
            # in production, throttle this (skip when last_used_at is recent) to
            # avoid a write per request
            await db.execute(
                update(ApiKey)
                .where(ApiKey.id == rec.api_key_id)
                .values(last_used_at=func.now())
            )
            await db.commit()
    except Exception:  # a logging failure must never surface on the request path
        log.exception("failed to record gateway request")
