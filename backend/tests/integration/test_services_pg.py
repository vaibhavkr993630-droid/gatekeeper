"""Service + API key persistence and FK cascade against real Postgres."""
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.service import ApiKey

SERVICE_BODY = {
    "name": "PG Service",
    "upstream_url": "https://pg-backend.example.com",
    "rule": {"algorithm": "token_bucket", "limit": 50, "window_seconds": 10, "burst": 60},
}


@pytest.mark.asyncio
async def test_service_and_key_cascade_on_postgres(pg_client: AsyncClient, pg_session):
    reg = await pg_client.post(
        "/api/auth/register",
        json={"tenant_name": "pgco", "email": "pg-svc@example.com", "password": "supersecret1"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    sid = (await pg_client.post("/api/services", json=SERVICE_BODY, headers=headers)).json()["id"]
    await pg_client.post(f"/api/services/{sid}/keys", json={"name": "k"}, headers=headers)

    assert (await pg_session.execute(select(func.count()).select_from(ApiKey))).scalar() == 1

    resp = await pg_client.delete(f"/api/services/{sid}", headers=headers)
    assert resp.status_code == 204
    # ondelete=CASCADE removes the dependent api_keys row
    assert (await pg_session.execute(select(func.count()).select_from(ApiKey))).scalar() == 0
