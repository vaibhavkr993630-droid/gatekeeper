# rate_limit/

Phase 3. Pluggable algorithms behind one interface:

    class RateLimiter(Protocol):
        async def check(self, key: str) -> RateLimitResult: ...   # (allowed, remaining, retry_after)

Planned: `token_bucket.py`, `sliding_window.py`. Atomicity via Redis Lua (`EVAL`)
so check-and-increment is a single atomic op under concurrent load. Not implemented yet.
