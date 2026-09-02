"""Shared interface for rate-limiting algorithms.

Every algorithm is a strategy behind one method: `check(key)`. The gateway (Phase 4)
picks an implementation from a service's configured policy via `get_rate_limiter`
and never branches on the algorithm itself.

Design notes worth defending:

* **Atomicity via Redis Lua.** A naive `GET count` -> decide in Python -> `INCR`
  is a check-then-act race: under concurrent load two requests both read count=99
  (limit 100), both decide "allowed", both increment -> 101. Redis runs a Lua
  script as one indivisible operation (no other command interleaves), so the
  read-decide-write happens atomically server-side. `test_rate_limit.py` proves
  this by firing hundreds of concurrent requests and asserting the count is exact.

* **Time is an argument, not `redis.call('TIME')`.** Passing `now` in from the
  caller keeps each script a pure function of its inputs: deterministic (safe
  under every Redis replication mode) and testable without sleeping — tests
  advance `now` to exercise window rollover and bucket refill.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    # seconds until a request of this cost would be admitted (0 when allowed)
    retry_after: float

    @property
    def rejected(self) -> bool:
        return not self.allowed


@runtime_checkable
class RateLimiter(Protocol):
    async def check(
        self, key: str, *, cost: int = 1, now: float | None = None
    ) -> RateLimitResult:
        """Attempt to consume `cost` units against `key`.

        `now` defaults to wall-clock seconds; tests pass an explicit value.
        """
        ...


def _resolve_now(now: float | None) -> float:
    return time.time() if now is None else now


def make_key(scope: str, identifier: str) -> str:
    """Redis key for one (service, client) pair.

    `{scope}` is a Redis Cluster hash tag: every key derived from the same scope
    (the sliding-window limiter uses several) hashes to one slot, so a future
    move to Cluster keeps a limiter's state co-located. Harmless on a single node.
    """
    return f"rl:{{{scope}}}:{identifier}"
