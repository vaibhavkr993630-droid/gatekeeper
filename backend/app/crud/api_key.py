from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import GeneratedApiKey, generate_api_key
from app.models.service import ApiKey


async def list_keys(db: AsyncSession, service_id: int) -> list[ApiKey]:
    res = await db.execute(
        select(ApiKey).where(ApiKey.service_id == service_id).order_by(ApiKey.id)
    )
    return list(res.scalars().all())


async def get_key(db: AsyncSession, *, key_id: int, service_id: int) -> ApiKey | None:
    res = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.service_id == service_id)
    )
    return res.scalar_one_or_none()


async def create_key(
    db: AsyncSession, *, service_id: int, name: str | None
) -> tuple[ApiKey, str]:
    """Returns the persisted row and the one-time plaintext key."""
    generated: GeneratedApiKey = generate_api_key()
    key = ApiKey(
        service_id=service_id,
        name=name,
        key_hash=generated.key_hash,
        prefix=generated.prefix,
        last_four=generated.last_four,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key, generated.plaintext


async def revoke_key(db: AsyncSession, key: ApiKey) -> None:
    await db.delete(key)
    await db.commit()
