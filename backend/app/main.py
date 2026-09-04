from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, services, stats
from app.core.config import settings
from app.core.redis import close_redis, get_redis
from app.gateway import router as gateway_router
from app.gateway.client import close_http_client
from app.ws import router as ws_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_http_client()
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
app.include_router(stats.router, prefix="/api")
app.include_router(gateway_router, prefix="/gw")
app.include_router(ws_router, prefix="/ws")


@app.get("/health", tags=["ops"])
async def health() -> dict[str, object]:
    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:  # noqa: BLE001 — health check must never raise
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
