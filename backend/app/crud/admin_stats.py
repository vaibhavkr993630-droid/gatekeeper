"""Platform-wide aggregates for the admin overview.

Deliberately separate from `crud/request_log.py` (tenant-scoped): every query
here returns counts/averages only — never a row with a path, client IP, or method
— matching the brief's "site reliability view, not snoop on tenant traffic".
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import daily_limit_for
from app.models.request_log import RequestLog
from app.models.service import Service
from app.models.tenant import Tenant

NEAR_LIMIT_THRESHOLD = 0.8
MAX_NEAR_LIMIT_ROWS = 20


async def counts(db: AsyncSession) -> tuple[int, int]:
    tenants_total = await db.scalar(select(func.count()).select_from(Tenant))
    services_total = await db.scalar(select(func.count()).select_from(Service))
    return tenants_total or 0, services_total or 0


async def traffic_summary_24h(db: AsyncSession) -> dict:
    since = datetime.now(UTC) - timedelta(hours=24)
    row = (
        await db.execute(
            select(
                func.count().label("requests"),
                func.count().filter(~RequestLog.allowed).label("blocked"),
                func.count()
                .filter(or_(~RequestLog.allowed, RequestLog.status_code >= 500))
                .label("errors"),
                func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
            ).where(RequestLog.created_at >= since)
        )
    ).one()
    requests = row.requests or 0
    return {
        "requests_24h": requests,
        "blocked_24h": row.blocked or 0,
        "error_rate_24h": round((row.errors or 0) / requests, 4) if requests else 0.0,
        "avg_latency_ms_24h": round(row.avg_latency_ms, 1) if row.avg_latency_ms else None,
    }


async def platform_requests_series(db: AsyncSession, *, minutes: int = 60) -> list[dict]:
    since = datetime.now(UTC) - timedelta(minutes=minutes)
    bucket = func.date_trunc("minute", RequestLog.created_at)
    res = await db.execute(
        select(
            bucket.label("minute"),
            func.count().label("requests"),
            func.count().filter(~RequestLog.allowed).label("blocked"),
        )
        .where(RequestLog.created_at >= since)
        .group_by(bucket)
        .order_by(bucket)
    )
    return [
        {"minute": r.minute.isoformat(), "requests": r.requests, "blocked": r.blocked}
        for r in res.all()
    ]


async def tenants_near_limit(db: AsyncSession) -> list[dict]:
    since = datetime.now(UTC) - timedelta(hours=24)
    res = await db.execute(
        select(Tenant.id, Tenant.name, Tenant.plan, func.count(RequestLog.id).label("n"))
        .join(RequestLog, RequestLog.tenant_id == Tenant.id)
        .where(RequestLog.created_at >= since)
        .group_by(Tenant.id, Tenant.name, Tenant.plan)
    )
    rows = []
    for tenant_id, name, plan, n in res.all():
        limit = daily_limit_for(plan)
        pct = n / limit if limit else 0.0
        if pct >= NEAR_LIMIT_THRESHOLD:
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "plan": plan,
                    "requests_24h": n,
                    "daily_limit": limit,
                    "pct_used": round(pct, 4),
                }
            )
    rows.sort(key=lambda r: r["pct_used"], reverse=True)
    return rows[:MAX_NEAR_LIMIT_ROWS]
