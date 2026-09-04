from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_log import RequestLog
from app.models.service import Service


async def recent_for_tenant(
    db: AsyncSession, tenant_id: int, *, limit: int = 50
) -> list[tuple[RequestLog, str]]:
    """Most recent requests across all of a tenant's services, newest first,
    each paired with its service name."""
    res = await db.execute(
        select(RequestLog, Service.name)
        .join(Service, Service.id == RequestLog.service_id)
        .where(RequestLog.tenant_id == tenant_id)
        .order_by(RequestLog.id.desc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in res.all()]


async def stats_for_service(
    db: AsyncSession, service_id: int, *, minutes: int = 60
) -> dict:
    since = datetime.now(UTC) - timedelta(minutes=minutes)
    bucket = func.date_trunc("minute", RequestLog.created_at)

    res = await db.execute(
        select(
            bucket.label("minute"),
            func.count().label("requests"),
            func.count().filter(~RequestLog.allowed).label("blocked"),
        )
        .where(RequestLog.service_id == service_id, RequestLog.created_at >= since)
        .group_by(bucket)
        .order_by(bucket)
    )
    series = [
        {"minute": r.minute.isoformat(), "requests": r.requests, "blocked": r.blocked}
        for r in res.all()
    ]
    total = sum(p["requests"] for p in series)
    blocked = sum(p["blocked"] for p in series)
    return {
        "window_minutes": minutes,
        "totals": {
            "requests": total,
            "blocked": blocked,
            "block_rate": round(blocked / total, 4) if total else 0.0,
        },
        "series": series,
    }
