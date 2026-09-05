from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser


async def get_admin_by_email(db: AsyncSession, email: str) -> AdminUser | None:
    res = await db.execute(select(AdminUser).where(AdminUser.email == email.lower()))
    return res.scalar_one_or_none()


async def get_admin(db: AsyncSession, admin_id: int) -> AdminUser | None:
    res = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    return res.scalar_one_or_none()
