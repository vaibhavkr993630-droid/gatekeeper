"""Auth flow exercised against real Postgres (schema, unique constraint, FK)."""
import pytest
from httpx import AsyncClient

REG = {"tenant_name": "Acme", "email": "pg-owner@example.com", "password": "supersecret1"}


@pytest.mark.asyncio
async def test_full_auth_flow_on_postgres(pg_client: AsyncClient):
    reg = await pg_client.post("/api/auth/register", json=REG)
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    # unique email constraint is enforced by the DB, not just app logic
    dup = await pg_client.post("/api/auth/register", json={**REG, "tenant_name": "Acme2"})
    assert dup.status_code == 409

    me = await pg_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["tenant"]["name"] == "Acme"

    login = await pg_client.post(
        "/api/auth/login", json={"email": REG["email"], "password": REG["password"]}
    )
    assert login.status_code == 200
