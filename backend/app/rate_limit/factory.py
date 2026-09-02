from redis.asyncio import Redis

from app.core.enums import RateLimitAlgorithm
from app.models.service import RateLimitRule
from app.rate_limit.base import RateLimiter
from app.rate_limit.sliding_window import SlidingWindowCounterLimiter
from app.rate_limit.token_bucket import TokenBucketLimiter


def get_rate_limiter(rule: RateLimitRule, redis: Redis) -> RateLimiter:
    """Map a service's stored policy onto a limiter instance.

    The gateway (Phase 4) calls this and then `.check(key)` — it never sees which
    algorithm is in play. Adding an algorithm means a new class + a case here.
    """
    if rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
        return TokenBucketLimiter(
            redis,
            # sustained rate; `burst` (or `limit`) is the bucket ceiling
            rate=rule.limit / rule.window_seconds,
            capacity=rule.burst or rule.limit,
        )
    if rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW_COUNTER:
        return SlidingWindowCounterLimiter(
            redis, limit=rule.limit, window_seconds=rule.window_seconds
        )
    raise ValueError(f"unknown rate-limit algorithm: {rule.algorithm!r}")
