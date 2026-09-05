"""Admin auth: separate login, and tokens that are not interchangeable with
tenant tokens (different signing key, not just a different claim)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.admin import AdminUser

ADMIN = {"email": "ops@example.com", "password": "supersecret1"}
TENANT_REG = {"tenant_name": "Acme", "email": "owner@example.com", "password": "supersecret1"}


async def _seed_admin(db: AsyncSession) -> None:
    db.add(AdminUser(email=ADMIN["email"], hashed_password=hash_password(ADMIN["password"])))
    await db.commit()


@pytest.mark.asyncio
async def test_admin_login_and_me(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)

    res = await client.post("/api/admin/auth/login", json=ADMIN)
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = await client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == ADMIN["email"]


@pytest.mark.asyncio
async def test_admin_login_rejects_bad_password(client: AsyncClient, db_session: AsyncSession):
    await _seed_admin(db_session)
    res = await client.post(
        "/api/admin/auth/login", json={"email": ADMIN["email"], "password": "wrong"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_route_requires_a_token(client: AsyncClient):
    assert (await client.get("/api/admin/me")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_tenant_token_is_rejected_on_admin_routes(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_admin(db_session)
    reg = await client.post("/api/auth/register", json=TENANT_REG)
    tenant_token = reg.json()["access_token"]

    res = await client.get("/api/admin/me", headers={"Authorization": f"Bearer {tenant_token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_token_is_rejected_on_tenant_routes(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_admin(db_session)
    login = await client.post("/api/admin/auth/login", json=ADMIN)
    admin_token = login.json()["access_token"]

    res = await client.get("/api/services", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_no_public_admin_registration_endpoint(client: AsyncClient):
    res = await client.post("/api/admin/auth/register", json=ADMIN)
    assert res.status_code == 404
