from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service import RateLimitRule, Service
from app.schemas.service import RuleIn, ServiceCreate, ServiceUpdate

_LOAD = (selectinload(Service.rule),)


async def list_services(db: AsyncSession, tenant_id: int) -> list[Service]:
    res = await db.execute(
        select(Service).options(*_LOAD).where(Service.tenant_id == tenant_id).order_by(Service.id)
    )
    return list(res.scalars().all())


async def get_service(db: AsyncSession, *, service_id: int, tenant_id: int) -> Service | None:
    """Tenant-scoped lookup — the only way services are fetched for dashboard routes."""
    res = await db.execute(
        select(Service)
        .options(*_LOAD)
        .where(Service.id == service_id, Service.tenant_id == tenant_id)
    )
    return res.scalar_one_or_none()


async def create_service(db: AsyncSession, *, tenant_id: int, data: ServiceCreate) -> Service:
    service = Service(
        tenant_id=tenant_id,
        name=data.name,
        upstream_url=str(data.upstream_url),
        rule=RateLimitRule(
            algorithm=data.rule.algorithm,
            limit=data.rule.limit,
            window_seconds=data.rule.window_seconds,
            burst=data.rule.burst,
        ),
    )
    db.add(service)
    await db.commit()
    await db.refresh(service, attribute_names=["rule"])
    return service


async def update_service(db: AsyncSession, service: Service, data: ServiceUpdate) -> Service:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, str(value) if field == "upstream_url" else value)
    await db.commit()
    await db.refresh(service, attribute_names=["rule"])
    return service


async def replace_rule(db: AsyncSession, service: Service, data: RuleIn) -> Service:
    service.rule.algorithm = data.algorithm
    service.rule.limit = data.limit
    service.rule.window_seconds = data.window_seconds
    service.rule.burst = data.burst
    await db.commit()
    await db.refresh(service, attribute_names=["rule"])
    return service


async def delete_service(db: AsyncSession, service: Service) -> None:
    await db.delete(service)
    await db.commit()
