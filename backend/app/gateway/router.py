"""The hot path: /gw/{public_id}/{path} -> auth -> rate check -> forward or 429.

Kept deliberately lean. Per request: one indexed DB read (API-key hash), one
Redis round-trip (the Lua check), then either a streamed upstream call or an
immediate 429. Persistence (RequestLog + key touch) runs as a background task
after the response, so the caller never waits on it.
"""
import logging
import math
import time

from fastapi import APIRouter, Request
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse, Response

from app.api.deps import DbDep, RedisDep
from app.core.config import settings
from app.gateway.forwarder import UpstreamError, forward
from app.gateway.http_util import client_ip_from, extract_api_key
from app.gateway.identity import GatewayAuthError, resolve_target
from app.gateway.recorder import RequestRecord, record_request
from app.rate_limit import make_key
from app.rate_limit.base import RateLimitResult
from app.rate_limit.factory import get_rate_limiter
from app.ws.broadcast import broadcast_request

log = logging.getLogger("gatekeeper.gateway")

router = APIRouter(tags=["gateway"])

_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def _rate_limit_headers(result: RateLimitResult) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(max(0, result.remaining)),
    }
    if not result.allowed:
        headers["Retry-After"] = str(max(1, math.ceil(result.retry_after)))
    return headers


@router.api_route("/{public_id}/{path:path}", methods=_METHODS)
async def gateway(public_id: str, path: str, request: Request, db: DbDep, redis: RedisDep) -> Response:
    client_ip = client_ip_from(
        forwarded_for=request.headers.get("x-forwarded-for"),
        peer=request.client.host if request.client else None,
        trust_forwarded=settings.trust_forwarded_for,
    )

    raw_key = extract_api_key(request.headers)
    if not raw_key:
        return JSONResponse(
            {"detail": "Missing API key"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- identify the service (not logged: no tenant to attribute a bad key to) ---
    try:
        target = await resolve_target(db, public_id=public_id, raw_api_key=raw_key)
    except GatewayAuthError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    background = BackgroundTasks()

    def _record(*, allowed: bool, status_code: int, latency_ms: int | None) -> None:
        record = RequestRecord(
            tenant_id=target.service.tenant_id,
            service_id=target.service.id,
            service_name=target.service.name,
            api_key_id=target.api_key_id,
            allowed=allowed,
            status_code=status_code,
            method=request.method,
            path="/" + path,
            client_ip=client_ip,
            rule_algorithm=str(target.rule.algorithm),
            latency_ms=latency_ms,
        )
        background.add_task(record_request, record)  # persist
        background.add_task(broadcast_request, record)  # push to live dashboards

    # --- rate limit ---
    limiter = get_rate_limiter(target.rule, redis)
    rl_key = make_key(target.service.public_id, client_ip)
    try:
        result: RateLimitResult | None = await limiter.check(rl_key)
    except Exception:  # noqa: BLE001 — Redis is down
        if not settings.rate_limit_fail_open:
            return JSONResponse({"detail": "Rate limiter unavailable"}, status_code=503)
        log.warning("rate limiter unavailable; failing open for service %s", target.service.public_id)
        result = None

    if result is not None and not result.allowed:
        _record(allowed=False, status_code=429, latency_ms=None)
        return JSONResponse(
            {"detail": "Rate limit exceeded", "retry_after": result.retry_after},
            status_code=429,
            headers=_rate_limit_headers(result),
            background=background,
        )

    # --- forward ---
    started = time.perf_counter()
    try:
        response = await forward(
            request,
            upstream_base=target.service.upstream_url,
            path=path,
            client_ip=client_ip,
            background=background,
        )
    except UpstreamError as exc:
        _record(allowed=True, status_code=exc.status_code, latency_ms=None)
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, background=background
        )

    latency_ms = int((time.perf_counter() - started) * 1000)  # upstream time-to-first-byte
    if result is not None:
        response.headers.update(_rate_limit_headers(result))
    elif settings.rate_limit_fail_open:
        response.headers["X-RateLimit-Bypassed"] = "true"

    _record(allowed=True, status_code=response.status_code, latency_ms=latency_ms)
    response.background = background
    return response
