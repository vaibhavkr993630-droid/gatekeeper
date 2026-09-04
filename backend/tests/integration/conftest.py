"""Integration fixtures — run against the real Postgres + Redis from docker-compose.

Each fixture auto-skips when its backend is unreachable, so `pytest` stays green
on a machine without the containers up. CI brings both service containers up first.
"""
import asyncio
import contextlib
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
import uvicorn
from httpx import ASGITransport, AsyncClient
from redis.asyncio import BlockingConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.api.deps import get_db, get_redis_client
from app.core.config import settings
from app.db.base import Base
from app.db.session import reset_db_engine
from app.gateway.client import close_http_client
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def _reset_shared_async_resources():
    """The app holds process-global async resources (db engine, httpx client) that
    bind to the first event loop that uses them. pytest-asyncio gives each test a
    fresh loop, so reset them around every test."""
    await reset_db_engine()
    await close_http_client()
    yield
    await reset_db_engine()
    await close_http_client()


@pytest_asyncio.fixture
async def pg_engine():
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Postgres not reachable for integration tests: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    """Each test runs in a transaction that is rolled back afterwards."""
    conn = await pg_engine.connect()
    trans = await conn.begin()
    maker = async_sessionmaker(bind=conn, expire_on_commit=False, autoflush=False, join_transaction_mode="create_savepoint")
    session = maker()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def pg_client(pg_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield pg_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def redis_client():
    """A flushed Redis for each test, backed by a *bounded* blocking pool.

    The concurrency tests fan out hundreds of `check()` calls at once; a bounded
    pool makes them queue on a connection (as a real service would) instead of
    opening a socket per task. Assumes a throwaway instance — FLUSHDB either side.
    """
    pool = BlockingConnectionPool.from_url(
        settings.redis_url, decode_responses=True, max_connections=32, timeout=20
    )
    client = Redis(connection_pool=pool)
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001
        await client.aclose()
        pytest.skip(f"Redis not reachable for integration tests: {exc}")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


# --- gateway (Phase 4) --------------------------------------------------------


@pytest_asyncio.fixture
async def stub_upstream() -> AsyncGenerator[str, None]:
    """A real HTTP server on an ephemeral port that echoes the request back,
    so gateway tests exercise actual network forwarding. `?status=NNN` sets the
    response code; `?sleep=S` delays the response."""

    async def echo(request):
        params = request.query_params
        if params.get("sleep"):
            await asyncio.sleep(float(params["sleep"]))
        body = await request.body()
        return JSONResponse(
            {
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query,
                "headers": {k.lower(): v for k, v in request.headers.items()},
                "body": body.decode(errors="replace"),
            },
            status_code=int(params.get("status", 200)),
        )

    methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    stub = Starlette(routes=[Route("/{path:path}", echo, methods=methods)])
    config = uvicorn.Config(stub, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.02)
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest_asyncio.fixture
async def gateway_client(
    pg_engine, redis_client: Redis
) -> AsyncGenerator[tuple[AsyncClient, async_sessionmaker], None]:
    """HTTP client wired to the app with a *real committing* DB session (the
    gateway's background tasks commit RequestLog rows) and the flushed test Redis.
    Tables are truncated afterwards."""
    maker = async_sessionmaker(pg_engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://gw") as ac:
            yield ac, maker
    finally:
        app.dependency_overrides.clear()
        async with pg_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.exec_driver_sql(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
