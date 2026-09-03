"""Process-wide httpx client for upstream forwarding.

One pooled client for the whole app — creating a client per request would throw
away keep-alive connections and dominate the hot path. Created lazily, closed on
app shutdown (see `app.main.lifespan`).
"""
import httpx

from app.core.config import settings

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.upstream_timeout_seconds),
            follow_redirects=False,  # pass 3xx straight back to the caller
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=40),
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
