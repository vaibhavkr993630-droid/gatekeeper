from redis.asyncio import Redis

from app.rate_limit._scripts import load
from app.rate_limit.base import RateLimitResult, _resolve_now

_LUA = load("sliding_window.lua")


class SlidingWindowCounterLimiter:
    """Fixed `limit` requests per rolling `window_seconds`, using the two-counter
    approximation (see `scripts/sliding_window.lua`).

    Unlike a fixed window it does not let a client spend a full quota at the end
    of one window and another full quota at the start of the next.
    """

    def __init__(self, redis: Redis, *, limit: int, window_seconds: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._redis = redis
        self._script = None  # registered lazily on first check (EVALSHA + fallback)
        self.limit = int(limit)
        self.window_seconds = int(window_seconds)

    async def check(
        self, key: str, *, cost: int = 1, now: float | None = None
    ) -> RateLimitResult:
        if cost < 1:
            raise ValueError("cost must be >= 1")
        if self._script is None:
            self._script = self._redis.register_script(_LUA)
        allowed, remaining, retry_after = await self._script(
            keys=[key],
            args=[_resolve_now(now), self.window_seconds, self.limit, cost],
        )
        return RateLimitResult(
            allowed=bool(int(allowed)),
            limit=self.limit,
            remaining=int(remaining),
            retry_after=float(retry_after),
        )
