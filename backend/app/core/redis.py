"""Async Redis client.

Redis plays one role in GateKeeper: the atomic counter store behind the rate
limiter (not caching, not pub/sub). A single shared client with a connection pool
is created lazily and reused for the process lifetime.
"""
from redis.asyncio import Redis, from_url

from app.core.config import settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        # decode_responses=True so Lua string returns arrive as `str`, not bytes.
        _client = from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
