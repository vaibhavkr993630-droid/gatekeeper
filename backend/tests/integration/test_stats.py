"""GET /api/services/{id}/stats — aggregates from RequestLog, tenant-scoped."""
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client, email: str) -> dict[str, str]:
    res = await client.post(
        "/api/auth/register",
        json={"tenant_name": email.split("@")[0], "email": email, "password": "supersecret1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _make_service(client, headers, stub_upstream, *, limit: int) -> tuple[int, str, str]:
    created = (
        await client.post(
            "/api/services",
            json={
                "name": "Svc",
                "upstream_url": stub_upstream,
                "rule": {"algorithm": "token_bucket", "limit": limit, "window_seconds": 60},
            },
            headers=headers,
        )
    ).json()
    key = (
        await client.post(f"/api/services/{created['id']}/keys", json={}, headers=headers)
    ).json()["api_key"]
    return created["id"], created["public_id"], key


async def test_stats_reflect_gateway_traffic(gateway_client, stub_upstream):
    client, _maker = gateway_client
    headers = await _login(client, "statsowner@example.com")
    sid, public_id, key = await _make_service(client, headers, stub_upstream, limit=2)

    for _ in range(4):  # 2 allowed, 2 blocked
        await client.get(f"/gw/{public_id}/y", headers={"X-API-Key": key})

    stats = await client.get(f"/api/services/{sid}/stats?minutes=60", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["totals"] == {"requests": 4, "blocked": 2, "block_rate": 0.5}
    assert body["rule"]["limit"] == 2
    assert sum(p["requests"] for p in body["series"]) == 4


async def test_stats_are_tenant_scoped(gateway_client, stub_upstream):
    client, _maker = gateway_client
    alice = await _login(client, "alice@example.com")
    bob = await _login(client, "bob@example.com")

    sid = (
        await client.post(
            "/api/services",
            json={
                "name": "Alice svc",
                "upstream_url": stub_upstream,
                "rule": {"algorithm": "sliding_window_counter", "limit": 10, "window_seconds": 60},
            },
            headers=alice,
        )
    ).json()["id"]

    assert (await client.get(f"/api/services/{sid}/stats", headers=bob)).status_code == 404
    assert (await client.get(f"/api/services/{sid}/stats", headers=alice)).status_code == 200
