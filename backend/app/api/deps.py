from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.core.security import JWTError, decode_access_token, decode_admin_token
from app.crud import admin as crud_admin
from app.crud import service as crud_service
from app.crud import tenant as crud_tenant
from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.service import Service
from app.models.tenant import TenantUser

_bearer = HTTPBearer(auto_error=True)

DbDep = Annotated[AsyncSession, Depends(get_db)]


def get_redis_client() -> Redis:
    """Thin DI wrapper so tests can override the Redis used by the gateway."""
    return get_redis()


RedisDep = Annotated[Redis, Depends(get_redis_client)]


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: DbDep,
) -> TenantUser:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise cred_exc

    user = await crud_tenant.get_user(db, user_id)
    if user is None or not user.is_active:
        raise cred_exc
    return user


CurrentUser = Annotated[TenantUser, Depends(get_current_user)]


async def get_owned_service(
    service_id: int,
    db: DbDep,
    current_user: CurrentUser,
) -> Service:
    """RBAC gate for every service-scoped route. Returns 404 (not 403) for a service
    owned by another tenant so existence isn't leaked across tenants.
    """
    service = await crud_service.get_service(
        db, service_id=service_id, tenant_id=current_user.tenant_id
    )
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return service


OwnedService = Annotated[Service, Depends(get_owned_service)]


async def get_current_admin(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: DbDep,
) -> AdminUser:
    """Verifies against `admin_secret_key` — a tenant JWT will never decode here,
    regardless of any claim it carries, because it's signed with a different key."""
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_admin_token(creds.credentials)
        if payload.get("scope") != "admin":
            raise cred_exc
        admin_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise cred_exc

    admin = await crud_admin.get_admin(db, admin_id)
    if admin is None or not admin.is_active:
        raise cred_exc
    return admin


CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]
