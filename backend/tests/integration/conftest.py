"""Integration fixtures — run against the real Postgres + Redis from docker-compose.

Each fixture auto-skips when its backend is unreachable, so `pytest` stays green
on a machine without the containers up. CI brings both service containers up first.
"""
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import BlockingConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.db.base import Base
from app.main import app


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
