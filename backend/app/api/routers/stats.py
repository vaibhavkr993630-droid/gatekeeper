from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbDep, OwnedService
from app.crud import request_log as crud_log
from app.schemas.stats import ServiceStats

router = APIRouter(prefix="/services", tags=["stats"])


@router.get("/{service_id}/stats", response_model=ServiceStats)
async def service_stats(
    service: OwnedService,
    db: DbDep,
    minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
) -> ServiceStats:
    data = await crud_log.stats_for_service(db, service.id, minutes=minutes)
    return ServiceStats(service_id=service.id, rule=service.rule, **data)
