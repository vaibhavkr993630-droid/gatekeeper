# rate_limit/

Pluggable rate-limiting algorithms behind one interface (`base.RateLimiter`):

```python
async def check(key: str, *, cost: int = 1, now: float | None = None) -> RateLimitResult
```

- `token_bucket.py` — burst-friendly; bucket of `capacity` tokens refilling at `rate`/s.
- `sliding_window.py` — `limit` per rolling `window_seconds`, two-counter approximation.
- `factory.get_rate_limiter(rule, redis)` — selects one from a service's stored policy.

Each `check` is a single Redis **Lua script** (`scripts/*.lua`) so read-decide-write is
atomic — no check-then-act race under concurrent load. `now` is passed in (not read from
`redis.call('TIME')`) to keep the scripts deterministic and testable without sleeping.

Correctness proof: `tests/integration/test_rate_limit.py` fires hundreds of concurrent
`check` calls and asserts the admitted count is exactly the limit.

Not yet wired to the gateway — that's Phase 4.
