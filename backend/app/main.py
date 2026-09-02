from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, services
from app.core.config import settings
from app.core.redis import close_redis, get_redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_redis()


app = FastAPI(title="GateKeeper", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(services.router, prefix="/api")


@app.get("/health", tags=["ops"])
async def health() -> dict[str, object]:
    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:  # noqa: BLE001 — health check must never raise
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
