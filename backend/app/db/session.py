from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_maker: async_sessionmaker[AsyncSession] | None = None


def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Lazily build the engine + sessionmaker on first use.

    Lazy so the async engine binds to whatever event loop first touches it — in
    production that's the single uvicorn loop; in tests it's each test's loop
    (with `reset_db_engine` clearing it between them).
    """
    global _engine, _maker
    if _maker is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _maker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _maker


def SessionLocal() -> AsyncSession:
    """A fresh session. Usage unchanged: `async with SessionLocal() as db: ...`."""
    return _sessionmaker()()


async def reset_db_engine() -> None:
    global _engine, _maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _maker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
