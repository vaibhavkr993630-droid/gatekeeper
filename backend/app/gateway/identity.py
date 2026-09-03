"""Resolve an inbound gateway request to the service it targets."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_api_key
from app.models.service import ApiKey, RateLimitRule, Service


class GatewayAuthError(Exception):
    """Request could not be attributed to an active service. Carries the HTTP
    status the gateway should return."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    service: Service
    rule: RateLimitRule
    api_key_id: int


async def resolve_target(
    db: AsyncSession, *, public_id: str, raw_api_key: str
) -> ResolvedTarget:
    """One indexed lookup on the key hash, then in-memory checks.

    The API key is the source of truth for *which* service; the `public_id` in
    the URL is confirmed against it (mismatch -> 404, as if the route doesn't exist).
    """
    res = await db.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.service).selectinload(Service.rule))
        .where(ApiKey.key_hash == hash_api_key(raw_api_key))
    )
    key = res.scalar_one_or_none()
    if key is None or not key.is_active:
        raise GatewayAuthError(401, "Invalid API key")

    service = key.service
    if service.public_id != public_id:
        raise GatewayAuthError(404, "No such gateway")
    if not service.is_active:
        raise GatewayAuthError(403, "Service is disabled")
    if service.rule is None:  # a service always has a rule, but guard the hot path
        raise GatewayAuthError(409, "Service has no rate-limit policy")

    return ResolvedTarget(service=service, rule=service.rule, api_key_id=key.id)
