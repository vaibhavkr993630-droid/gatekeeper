import pytest
from httpx import AsyncClient

SERVICE_BODY = {
    "name": "Payments API",
    "upstream_url": "https://backend.internal.example.com",
    "rule": {"algorithm": "sliding_window_counter", "limit": 100, "window_seconds": 60},
}


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    res = await client.post(
        "/api/auth/register",
        json={"tenant_name": email.split("@")[0], "email": email, "password": "supersecret1"},
    )
    assert res.status_code == 201
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_and_get_service(client: AsyncClient):
    headers = await _register(client, "alice@example.com")

    res = await client.post("/api/services", json=SERVICE_BODY, headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["rule"]["limit"] == 100
    assert len(body["public_id"]) == 24
    sid = body["id"]

    got = await client.get(f"/api/services/{sid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["name"] == "Payments API"


@pytest.mark.asyncio
async def test_rbac_tenant_isolation(client: AsyncClient):
    alice = await _register(client, "alice@example.com")
    bob = await _register(client, "bob@example.com")

    sid = (await client.post("/api/services", json=SERVICE_BODY, headers=alice)).json()["id"]

    # Bob sees none of Alice's services and cannot fetch one by id
    assert (await client.get("/api/services", headers=bob)).json() == []
    assert (await client.get(f"/api/services/{sid}", headers=bob)).status_code == 404
    assert (await client.delete(f"/api/services/{sid}", headers=bob)).status_code == 404


@pytest.mark.asyncio
async def test_update_service_and_rule(client: AsyncClient):
    headers = await _register(client, "alice@example.com")
    sid = (await client.post("/api/services", json=SERVICE_BODY, headers=headers)).json()["id"]

    patched = await client.patch(
        f"/api/services/{sid}", json={"name": "Renamed", "is_active": False}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed" and patched.json()["is_active"] is False

    ruled = await client.put(
        f"/api/services/{sid}/rule",
        json={"algorithm": "token_bucket", "limit": 10, "window_seconds": 1, "burst": 20},
        headers=headers,
    )
    assert ruled.status_code == 200
    assert ruled.json()["rule"] == {
        "algorithm": "token_bucket",
        "limit": 10,
        "window_seconds": 1,
        "burst": 20,
    }


@pytest.mark.asyncio
async def test_invalid_rule_rejected(client: AsyncClient):
    headers = await _register(client, "alice@example.com")
    bad = {**SERVICE_BODY, "rule": {"algorithm": "token_bucket", "limit": 100, "window_seconds": 0}}
    assert (await client.post("/api/services", json=bad, headers=headers)).status_code == 422

    bad_burst = {
        **SERVICE_BODY,
        "rule": {"algorithm": "token_bucket", "limit": 100, "window_seconds": 60, "burst": 10},
    }
    assert (await client.post("/api/services", json=bad_burst, headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_api_key_lifecycle(client: AsyncClient):
    headers = await _register(client, "alice@example.com")
    sid = (await client.post("/api/services", json=SERVICE_BODY, headers=headers)).json()["id"]

    created = await client.post(
        f"/api/services/{sid}/keys", json={"name": "prod"}, headers=headers
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["api_key"].startswith("gk_")
    assert payload["prefix"] == payload["api_key"][:11]
    assert payload["last_four"] == payload["api_key"][-4:]
    key_id = payload["id"]

    listed = await client.get(f"/api/services/{sid}/keys", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "api_key" not in listed.json()[0]  # plaintext never returned again

    revoked = await client.delete(f"/api/services/{sid}/keys/{key_id}", headers=headers)
    assert revoked.status_code == 204
    assert (await client.get(f"/api/services/{sid}/keys", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_requires_auth(client: AsyncClient):
    assert (await client.get("/api/services")).status_code in (401, 403)
    assert (await client.post("/api/services", json=SERVICE_BODY)).status_code in (401, 403)
