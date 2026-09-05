"""Platform admin API. Separate auth plane from `/api/auth` + `/api/services`:
admin tokens are signed with a different secret (`app/core/security.py`) and
there is no public registration endpoint here — see `scripts/create_admin.py`.

Every response is an aggregate. No route here returns a RequestLog row, a client
IP, a path, or anything else tied to one tenant's individual traffic.
"""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentAdmin, DbDep, RedisDep
from app.core.security import create_admin_token, verify_password
from app.crud import admin as crud_admin
from app.crud import admin_stats
from app.schemas.admin import AdminLoginRequest, AdminOut, AdminToken, SystemOverview

router = APIRouter(prefix="/admin", tags=["admin"])

_EMPTY_TRAFFIC = {
    "requests_24h": 0,
    "blocked_24h": 0,
    "error_rate_24h": 0.0,
    "avg_latency_ms_24h": None,
}


@router.post("/auth/login", response_model=AdminToken)
async def login(body: AdminLoginRequest, db: DbDep) -> AdminToken:
    admin = await crud_admin.get_admin_by_email(db, body.email)
    if admin is None or not verify_password(body.password, admin.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return AdminToken(access_token=create_admin_token(admin_id=admin.id))


@router.get("/me", response_model=AdminOut)
async def me(current_admin: CurrentAdmin) -> AdminOut:
    return current_admin


@router.get("/overview", response_model=SystemOverview)
async def overview(_current_admin: CurrentAdmin, db: DbDep, redis: RedisDep) -> SystemOverview:
    """Ops health view: stays up (reporting `db_ok`/`redis_ok`) even if one
    backend is degraded, rather than 500ing the whole dashboard."""
    try:
        tenants_total, services_total = await admin_stats.counts(db)
        traffic = await admin_stats.traffic_summary_24h(db)
        series = await admin_stats.platform_requests_series(db, minutes=60)
        near_limit = await admin_stats.tenants_near_limit(db)
        db_ok = True
    except Exception:  # noqa: BLE001 — degrade, don't 500 the ops view
        tenants_total, services_total = 0, 0
        traffic, series, near_limit = dict(_EMPTY_TRAFFIC), [], []
        db_ok = False

    try:
        await redis.ping()
        redis_ok = True
    except Exception:  # noqa: BLE001
        redis_ok = False

    return SystemOverview(
        tenants_total=tenants_total,
        services_total=services_total,
        redis_ok=redis_ok,
        db_ok=db_ok,
        requests_series_60m=series,
        tenants_near_limit=near_limit,
        **traffic,
    )
