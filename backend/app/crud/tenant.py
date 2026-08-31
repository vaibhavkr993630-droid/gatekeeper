from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tenant import Tenant, TenantUser


async def get_user_by_email(db: AsyncSession, email: str) -> TenantUser | None:
    res = await db.execute(
        select(TenantUser)
        .options(selectinload(TenantUser.tenant))
        .where(TenantUser.email == email.lower())
    )
    return res.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: int) -> TenantUser | None:
    res = await db.execute(
        select(TenantUser)
        .options(selectinload(TenantUser.tenant))
        .where(TenantUser.id == user_id)
    )
    return res.scalar_one_or_none()


async def create_tenant_with_owner(
    db: AsyncSession, *, tenant_name: str, email: str, hashed_password: str
) -> TenantUser:
    tenant = Tenant(name=tenant_name)
    user = TenantUser(email=email.lower(), hashed_password=hashed_password, tenant=tenant)
    db.add(tenant)
    db.add(user)
    await db.commit()
    await db.refresh(user, attribute_names=["tenant"])
    return user
