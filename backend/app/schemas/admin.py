from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.auth import Token


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminToken(Token):
    pass


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class TenantUsage(BaseModel):
    tenant_id: int
    name: str
    plan: str
    requests_24h: int
    daily_limit: int
    pct_used: float


class StatPoint(BaseModel):
    minute: str
    requests: int
    blocked: int


class SystemOverview(BaseModel):
    tenants_total: int
    services_total: int
    requests_24h: int
    blocked_24h: int
    error_rate_24h: float
    avg_latency_ms_24h: float | None
    redis_ok: bool
    db_ok: bool
    requests_series_60m: list[StatPoint]
    tenants_near_limit: list[TenantUsage]
