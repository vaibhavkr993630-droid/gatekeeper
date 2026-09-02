"""Rate-limiter correctness against real Redis.

The headline tests fire many `check()` calls concurrently via `asyncio.gather` and
assert the admitted count is *exact*. With a naive GET-decide-INCR in Python these
would over-admit; they pass only because each check is one atomic Lua script.
"""
import asyncio

import pytest

from app.rate_limit import RateLimiter, SlidingWindowCounterLimiter, TokenBucketLimiter

pytestmark = pytest.mark.asyncio

FIXED_NOW = 1_700_000_000.0  # any fixed instant; keeps concurrency tests about atomicity


async def _admit(limiter: RateLimiter, key: str, n: int, *, now: float) -> int:
    """Sequential attempts; returns how many were allowed."""
    allowed = 0
    for _ in range(n):
        result = await limiter.check(key, now=now)
        allowed += int(result.allowed)
    return allowed


# --- token bucket ---------------------------------------------------------


async def test_token_bucket_exact_under_concurrency(redis_client):
    limiter = TokenBucketLimiter(redis_client, rate=1.0, capacity=100)

    results = await asyncio.gather(
        *(limiter.check("svc:client", now=FIXED_NOW) for _ in range(250))
    )

    assert sum(r.allowed for r in results) == 100
    assert all(r.retry_after > 0 for r in results if not r.allowed)
    assert all(r.remaining >= 0 for r in results)
    assert min(r.remaining for r in results) == 0


async def test_token_bucket_refills_at_rate(redis_client):
    limiter = TokenBucketLimiter(redis_client, rate=10.0, capacity=50)
    t = 5_000.0

    assert await _admit(limiter, "k", 50, now=t) == 50
    assert not (await limiter.check("k", now=t)).allowed

    t += 2.0  # 10 tokens/s * 2s = 20 back
    assert await _admit(limiter, "k", 30, now=t) == 20


async def test_token_bucket_never_exceeds_capacity(redis_client):
    limiter = TokenBucketLimiter(redis_client, rate=100.0, capacity=10)

    assert (await limiter.check("k", now=0.0)).allowed  # seeds the bucket
    # an hour idle still only refills to `capacity`
    assert await _admit(limiter, "k", 25, now=3_600.0) == 10


async def test_token_bucket_retry_after_is_sane(redis_client):
    limiter = TokenBucketLimiter(redis_client, rate=2.0, capacity=4)
    await _admit(limiter, "k", 4, now=100.0)

    rejected = await limiter.check("k", now=100.0)
    assert not rejected.allowed
    # need 1 token back at 2/s -> ~0.5s
    assert 0.4 <= rejected.retry_after <= 0.6


# --- sliding window counter ----------------------------------------------


async def test_sliding_window_exact_under_concurrency(redis_client):
    limiter = SlidingWindowCounterLimiter(redis_client, limit=100, window_seconds=60)

    results = await asyncio.gather(
        *(limiter.check("k", now=FIXED_NOW) for _ in range(250))
    )

    assert sum(r.allowed for r in results) == 100


async def test_sliding_window_rolls_over(redis_client):
    limiter = SlidingWindowCounterLimiter(redis_client, limit=10, window_seconds=10)
    now = 1_000.0  # window index 100, fraction 0

    assert await _admit(limiter, "k", 10, now=now) == 10
    assert not (await limiter.check("k", now=now)).allowed

    now += 20.0  # two windows on: prev and cur both empty
    assert (await limiter.check("k", now=now)).allowed


async def test_sliding_window_smooths_the_boundary(redis_client):
    """A fixed window would let a client spend 100 at t=59s and another 100 at
    t=61s. The sliding counter still weights the previous window, so right after
    the boundary only a trickle gets through."""
    limiter = SlidingWindowCounterLimiter(redis_client, limit=100, window_seconds=60)

    fill = 60_000.0  # window index 1000, fraction 0
    assert await _admit(limiter, "k", 100, now=fill) == 100

    just_after = 60_061.0  # ~1s into window 1001; estimate ~ 100 * (1 - 1/60) ~ 98.3
    assert await _admit(limiter, "k", 100, now=just_after) < 10


async def test_sliding_window_isolates_keys(redis_client):
    limiter = SlidingWindowCounterLimiter(redis_client, limit=3, window_seconds=60)
    now = 900.0

    assert await _admit(limiter, "client:a", 5, now=now) == 3
    # a different client's key is unaffected
    assert (await limiter.check("client:b", now=now)).allowed


# --- why the Lua matters -------------------------------------------------


async def test_naive_check_then_incr_over_admits(redis_client):
    """Counter-example: GET -> decide in Python -> INCR is a check-then-act race.
    Under concurrency many tasks read the same count before any of them writes,
    so the limit is blown. This is exactly what the atomic Lua scripts prevent —
    contrast with `test_*_exact_under_concurrency` above."""
    limit = 100

    async def naive_check() -> bool:
        count = int(await redis_client.get("naive") or 0)
        if count >= limit:
            return False
        await asyncio.sleep(0)  # any await between decide and write is the race window
        await redis_client.incr("naive")
        return True

    results = await asyncio.gather(*(naive_check() for _ in range(250)))
    assert sum(results) > limit  # over-admitted; the bug is real
