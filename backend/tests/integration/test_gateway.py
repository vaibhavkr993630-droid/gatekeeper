"""End-to-end gateway path: real Postgres + Redis + a real upstream server."""
import pytest
from sqlalchemy import func, select

from app.core.security import generate_api_key
from app.models.request_log import RequestLog
from app.models.service import ApiKey, RateLimitRule, Service
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


async def _seed(maker, *, upstream: str, algorithm="token_bucket", limit=5, window=60, burst=None):
    """Insert a tenant + service + one API key; return the plaintext key + public_id."""
    generated = generate_api_key()
    async with maker() as db:
        tenant = Tenant(name="Acme")
        db.add(tenant)
        await db.flush()
        service = Service(
            tenant_id=tenant.id,
            name="Acme API",
            upstream_url=upstream,
            rule=RateLimitRule(
                algorithm=algorithm, limit=limit, window_seconds=window, burst=burst
            ),
        )
        db.add(service)
        await db.flush()
        db.add(
            ApiKey(
                service_id=service.id,
                key_hash=generated.key_hash,
                prefix=generated.prefix,
                last_four=generated.last_four,
            )
        )
        await db.commit()
        return generated.plaintext, service.public_id


async def test_forwards_allowed_request(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, public_id = await _seed(maker, upstream=stub_upstream)

    resp = await client.post(
        f"/gw/{public_id}/v1/things?limit=2",
        headers={"Authorization": f"Bearer {key}"},  # Bearer form also authenticates
        content=b'{"hello":"world"}',
    )

    assert resp.status_code == 200
    echoed = resp.json()
    assert echoed["method"] == "POST"
    assert echoed["path"] == "/v1/things"
    assert echoed["query"] == "limit=2"
    assert echoed["body"] == '{"hello":"world"}'
    assert "x-api-key" not in echoed["headers"]
    assert "authorization" not in echoed["headers"]  # gateway credential, not forwarded
    assert echoed["headers"]["x-forwarded-for"]
    assert resp.headers["x-ratelimit-limit"] == "5"
    assert int(resp.headers["x-ratelimit-remaining"]) == 4


async def test_enforces_the_limit(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, public_id = await _seed(maker, upstream=stub_upstream, algorithm="token_bucket", limit=3)

    codes = [
        (await client.get(f"/gw/{public_id}/", headers={"X-API-Key": key})).status_code
        for _ in range(6)
    ]
    assert codes.count(200) == 3
    assert codes.count(429) == 3

    blocked = await client.get(f"/gw/{public_id}/", headers={"X-API-Key": key})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


async def test_records_every_request(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, public_id = await _seed(maker, upstream=stub_upstream, limit=2)

    for _ in range(3):  # 2 allowed, 1 blocked
        await client.get(f"/gw/{public_id}/ping", headers={"X-API-Key": key})

    async with maker() as db:
        rows = (await db.execute(select(RequestLog).order_by(RequestLog.id))).scalars().all()
        assert len(rows) == 3
        assert [r.allowed for r in rows] == [True, True, False]
        assert [r.status_code for r in rows] == [200, 200, 429]
        assert all(r.path == "/ping" and r.method == "GET" for r in rows)
        assert all(r.rule_algorithm == "token_bucket" for r in rows)

        key_row = (await db.execute(select(ApiKey))).scalar_one()
        assert key_row.last_used_at is not None


async def test_rejects_missing_and_bad_key(gateway_client, stub_upstream):
    client, maker = gateway_client
    _key, public_id = await _seed(maker, upstream=stub_upstream)

    assert (await client.get(f"/gw/{public_id}/x")).status_code == 401
    assert (
        await client.get(f"/gw/{public_id}/x", headers={"X-API-Key": "gk_nope"})
    ).status_code == 401


async def test_key_for_other_service_is_404(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, _ = await _seed(maker, upstream=stub_upstream)

    resp = await client.get("/gw/deadbeefdeadbeefdeadbeef/x", headers={"X-API-Key": key})
    assert resp.status_code == 404


async def test_upstream_status_passthrough(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, public_id = await _seed(maker, upstream=stub_upstream, limit=50)

    resp = await client.get(f"/gw/{public_id}/thing?status=503", headers={"X-API-Key": key})
    assert resp.status_code == 503


async def test_upstream_unreachable_is_502(gateway_client):
    client, maker = gateway_client
    # nothing is listening on this port
    key, public_id = await _seed(maker, upstream="http://127.0.0.1:9", limit=50)

    resp = await client.get(f"/gw/{public_id}/x", headers={"X-API-Key": key})
    assert resp.status_code == 502

    async with maker() as db:
        row = (await db.execute(select(RequestLog))).scalar_one()
        assert row.status_code == 502 and row.allowed is True


async def test_disabled_service_is_403(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, public_id = await _seed(maker, upstream=stub_upstream)
    async with maker() as db:
        await db.execute(
            Service.__table__.update().values(is_active=False).where(Service.public_id == public_id)
        )
        await db.commit()

    resp = await client.get(f"/gw/{public_id}/x", headers={"X-API-Key": key})
    assert resp.status_code == 403


async def test_sliding_window_algorithm_through_gateway(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, public_id = await _seed(
        maker, upstream=stub_upstream, algorithm="sliding_window_counter", limit=4, window=60
    )
    codes = [
        (await client.get(f"/gw/{public_id}/", headers={"X-API-Key": key})).status_code
        for _ in range(6)
    ]
    assert codes.count(200) == 4
    assert codes.count(429) == 2

    async with maker() as db:
        n = await db.scalar(select(func.count()).select_from(RequestLog))
        assert n == 6
