import asyncio

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbDep, OwnedService
from app.core.config import settings
from app.core.net_safety import UnsafeUpstreamError, assert_public_upstream
from app.crud import api_key as crud_api_key
from app.crud import service as crud_service
from app.schemas.service import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    RuleIn,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
)

router = APIRouter(prefix="/services", tags=["services"])


async def _guard_upstream(url: str) -> None:
    """DNS resolution is blocking I/O — off the event loop via a thread. No-op
    unless `block_private_upstreams` is on (see config.py)."""
    if not settings.block_private_upstreams:
        return
    try:
        await asyncio.to_thread(assert_public_upstream, url)
    except UnsafeUpstreamError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("", response_model=list[ServiceOut])
async def list_services(current_user: CurrentUser, db: DbDep) -> list[ServiceOut]:
    return await crud_service.list_services(db, current_user.tenant_id)


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(body: ServiceCreate, current_user: CurrentUser, db: DbDep) -> ServiceOut:
    await _guard_upstream(str(body.upstream_url))
    return await crud_service.create_service(db, tenant_id=current_user.tenant_id, data=body)


@router.get("/{service_id}", response_model=ServiceOut)
async def get_service(service: OwnedService) -> ServiceOut:
    return service


@router.patch("/{service_id}", response_model=ServiceOut)
async def update_service(body: ServiceUpdate, service: OwnedService, db: DbDep) -> ServiceOut:
    if body.upstream_url is not None:
        await _guard_upstream(str(body.upstream_url))
    return await crud_service.update_service(db, service, body)


@router.put("/{service_id}/rule", response_model=ServiceOut)
async def replace_rule(body: RuleIn, service: OwnedService, db: DbDep) -> ServiceOut:
    return await crud_service.replace_rule(db, service, body)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(service: OwnedService, db: DbDep) -> None:
    await crud_service.delete_service(db, service)


# --- API keys (nested under a service) -------------------------------------


@router.get("/{service_id}/keys", response_model=list[ApiKeyOut])
async def list_keys(service: OwnedService, db: DbDep) -> list[ApiKeyOut]:
    return await crud_api_key.list_keys(db, service.id)


@router.post(
    "/{service_id}/keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED
)
async def create_key(body: ApiKeyCreate, service: OwnedService, db: DbDep) -> ApiKeyCreated:
    key, plaintext = await crud_api_key.create_key(db, service_id=service.id, name=body.name)
    return ApiKeyCreated(api_key=plaintext, **ApiKeyOut.model_validate(key).model_dump())


@router.delete(
    "/{service_id}/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_key(key_id: int, service: OwnedService, db: DbDep) -> None:
    key = await crud_api_key.get_key(db, key_id=key_id, service_id=service.id)
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await crud_api_key.revoke_key(db, key)
