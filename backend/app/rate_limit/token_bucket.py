from redis.asyncio import Redis

from app.rate_limit._scripts import load
from app.rate_limit.base import RateLimitResult, _resolve_now

_LUA = load("token_bucket.lua")


class TokenBucketLimiter:
    """Smooth rate limiting: a bucket of `capacity` tokens refilling at `rate`/sec.

    Allows short bursts up to `capacity` while holding the long-run average at
    `rate`. Good default when clients legitimately spike.
    """

    def __init__(
        self, redis: Redis, *, rate: float, capacity: int, ttl: int | None = None
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be > 0")
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._redis = redis
        self._script = None  # registered lazily on first check (EVALSHA + fallback)
        self.rate = float(rate)
        self.capacity = int(capacity)
        # keep an idle bucket around long enough that it would have refilled fully
        self.ttl = ttl or max(60, int(self.capacity / self.rate) * 2 + 60)

    async def check(
        self, key: str, *, cost: int = 1, now: float | None = None
    ) -> RateLimitResult:
        if cost < 1:
            raise ValueError("cost must be >= 1")
        if self._script is None:
            self._script = self._redis.register_script(_LUA)
        allowed, remaining, retry_after = await self._script(
            keys=[key],
            args=[self.rate, self.capacity, _resolve_now(now), cost, self.ttl],
        )
        return RateLimitResult(
            allowed=bool(int(allowed)),
            limit=self.capacity,
            remaining=int(remaining),
            retry_after=float(retry_after),
        )
