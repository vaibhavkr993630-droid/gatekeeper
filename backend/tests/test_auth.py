import pytest
from httpx import AsyncClient

REG = {"tenant_name": "Acme", "email": "owner@example.com", "password": "supersecret1"}


async def _register(client: AsyncClient, **overrides) -> dict:
    body = {**REG, **overrides}
    return await client.post("/api/auth/register", json=body)


@pytest.mark.asyncio
async def test_register_returns_token(client: AsyncClient):
    res = await _register(client)
    assert res.status_code == 201
    assert res.json()["access_token"]


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient):
    await _register(client)
    res = await _register(client, tenant_name="Acme2")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_ok_and_bad_password(client: AsyncClient):
    await _register(client)
    ok = await client.post("/api/auth/login", json={"email": REG["email"], "password": REG["password"]})
    assert ok.status_code == 200 and ok.json()["access_token"]

    bad = await client.post("/api/auth/login", json={"email": REG["email"], "password": "wrong"})
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token_and_scopes_to_tenant(client: AsyncClient):
    token = (await _register(client)).json()["access_token"]

    assert (await client.get("/api/auth/me")).status_code in (401, 403)  # no bearer

    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == REG["email"]
    assert body["tenant"]["name"] == "Acme"

    bogus = await client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert bogus.status_code == 401
