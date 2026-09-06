"""The SSRF guard wired into POST/PATCH /services — off by default, on when
`block_private_upstreams` is set (see app/core/config.py for why)."""
import pytest
from httpx import AsyncClient

from app.core.config import settings

REG = {"tenant_name": "Acme", "email": "owner@example.com", "password": "supersecret1"}


async def _auth_headers(client: AsyncClient) -> dict[str, str]:
    res = await client.post("/api/auth/register", json=REG)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


SERVICE_BODY = {
    "name": "Svc",
    "upstream_url": "http://127.0.0.1:9999",
    "rule": {"algorithm": "token_bucket", "limit": 10, "window_seconds": 60},
}


@pytest.mark.asyncio
async def test_loopback_upstream_allowed_when_guard_is_off(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "block_private_upstreams", False)
    headers = await _auth_headers(client)
    res = await client.post("/api/services", json=SERVICE_BODY, headers=headers)
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_loopback_upstream_rejected_when_guard_is_on(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "block_private_upstreams", True)
    headers = await _auth_headers(client)
    res = await client.post("/api/services", json=SERVICE_BODY, headers=headers)
    assert res.status_code == 422
    assert "non-routable" in res.json()["detail"]


@pytest.mark.asyncio
async def test_guard_also_applies_to_patch(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "block_private_upstreams", False)
    headers = await _auth_headers(client)
    created = await client.post("/api/services", json=SERVICE_BODY, headers=headers)
    service_id = created.json()["id"]

    monkeypatch.setattr(settings, "block_private_upstreams", True)
    res = await client.patch(
        f"/api/services/{service_id}",
        json={"upstream_url": "http://169.254.169.254/latest/meta-data"},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_public_upstream_always_allowed(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "block_private_upstreams", True)
    headers = await _auth_headers(client)
    # a literal public IP — no DNS involved, keeps this test network-free
    res = await client.post(
        "/api/services",
        json={**SERVICE_BODY, "upstream_url": "http://8.8.8.8"},
        headers=headers,
    )
    assert res.status_code == 201
