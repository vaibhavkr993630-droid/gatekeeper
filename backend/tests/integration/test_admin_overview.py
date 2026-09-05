"""GET /api/admin/overview — platform aggregates, real DB + Redis.

Confirms the numbers reflect real gateway traffic, the response never leaks a
per-request detail (path/IP), and the near-limit flag fires for an over-quota tenant.
"""
import json

import pytest

from app.core.security import hash_password
from app.models.admin import AdminUser
from app.models.request_log import RequestLog
from app.models.service import RateLimitRule, Service
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


async def _create_admin(maker, email: str, password: str) -> None:
    async with maker() as db:
        db.add(AdminUser(email=email, hashed_password=hash_password(password)))
        await db.commit()


async def _admin_headers(client, email: str, password: str) -> dict[str, str]:
    res = await client.post("/api/admin/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _tenant_headers(client, email: str) -> dict[str, str]:
    res = await client.post(
        "/api/auth/register",
        json={"tenant_name": email.split("@")[0], "email": email, "password": "supersecret1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_overview_reflects_traffic_with_no_per_request_detail(gateway_client, stub_upstream):
    client, maker = gateway_client
    await _create_admin(maker, "ops@example.com", "supersecret1")
    admin_headers = await _admin_headers(client, "ops@example.com", "supersecret1")
    tenant_headers = await _tenant_headers(client, "acme@example.com")

    created = (
        await client.post(
            "/api/services",
            json={
                "name": "svc",
                "upstream_url": stub_upstream,
                "rule": {"algorithm": "token_bucket", "limit": 2, "window_seconds": 60},
            },
            headers=tenant_headers,
        )
    ).json()
    key = (
        await client.post(f"/api/services/{created['id']}/keys", json={}, headers=tenant_headers)
    ).json()["api_key"]

    for _ in range(4):  # 2 allowed, 2 blocked
        await client.get(f"/gw/{created['public_id']}/very/secret/path", headers={"X-API-Key": key})

    resp = await client.get("/api/admin/overview", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["tenants_total"] >= 1
    assert body["services_total"] >= 1
    assert body["requests_24h"] >= 4
    assert body["blocked_24h"] >= 2
    assert 0.0 < body["error_rate_24h"] <= 1.0
    assert body["redis_ok"] is True
    assert body["db_ok"] is True
    assert sum(p["requests"] for p in body["requests_series_60m"]) >= 4

    dumped = json.dumps(body)
    assert "very/secret/path" not in dumped  # no path
    assert "acme" not in dumped.lower()  # no tenant/user identifying strings beyond aggregates


async def test_overview_requires_admin_auth(gateway_client):
    client, _maker = gateway_client
    assert (await client.get("/api/admin/overview")).status_code in (401, 403)

    tenant_headers = await _tenant_headers(client, "notadmin@example.com")
    resp = await client.get("/api/admin/overview", headers=tenant_headers)
    assert resp.status_code == 401


async def test_overview_flags_tenant_near_its_plan_limit(gateway_client):
    client, maker = gateway_client
    await _create_admin(maker, "ops2@example.com", "supersecret1")
    admin_headers = await _admin_headers(client, "ops2@example.com", "supersecret1")

    async with maker() as db:
        tenant = Tenant(name="SmallPlan", plan="free")  # free = 1000 req/day
        db.add(tenant)
        await db.flush()
        service = Service(
            tenant_id=tenant.id,
            name="svc",
            upstream_url="http://unused.example.com",
            rule=RateLimitRule(algorithm="token_bucket", limit=10_000, window_seconds=60, burst=None),
        )
        db.add(service)
        await db.flush()
        db.add_all(
            RequestLog(
                tenant_id=tenant.id,
                service_id=service.id,
                allowed=True,
                status_code=200,
                method="GET",
                path="/x",
                client_ip="203.0.113.5",
                rule_algorithm="token_bucket",
                latency_ms=5,
            )
            for _ in range(850)  # 85% of the 1000/day free quota
        )
        await db.commit()

    resp = await client.get("/api/admin/overview", headers=admin_headers)
    near = resp.json()["tenants_near_limit"]
    match = next((t for t in near if t["name"] == "SmallPlan"), None)
    assert match is not None
    assert match["plan"] == "free"
    assert match["requests_24h"] == 850
    assert match["daily_limit"] == 1000
    assert match["pct_used"] == pytest.approx(0.85)
