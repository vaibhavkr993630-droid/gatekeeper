"""Shape of the events pushed over the dashboard WebSocket."""
from datetime import UTC, datetime

from app.models.request_log import RequestLog


def request_event(
    *,
    service_id: int,
    service_name: str,
    allowed: bool,
    status_code: int,
    method: str,
    path: str,
    client_ip: str,
    rule_algorithm: str | None,
    latency_ms: int | None,
    occurred_at: datetime | None = None,
) -> dict:
    return {
        "type": "request",
        "service_id": service_id,
        "service_name": service_name,
        "allowed": allowed,
        "status_code": status_code,
        "method": method,
        "path": path,
        "client_ip": client_ip,
        "rule_algorithm": rule_algorithm,
        "latency_ms": latency_ms,
        "at": (occurred_at or datetime.now(UTC)).isoformat(),
    }


def event_from_log(row: RequestLog, service_name: str) -> dict:
    return request_event(
        service_id=row.service_id,
        service_name=service_name,
        allowed=row.allowed,
        status_code=row.status_code,
        method=row.method,
        path=row.path,
        client_ip=row.client_ip,
        rule_algorithm=row.rule_algorithm,
        latency_ms=row.latency_ms,
        occurred_at=row.created_at,
    )
