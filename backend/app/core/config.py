from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Signed with a *different* key than tenant tokens (app/core/security.py) —
    # not just a different claim. A leaked/forged tenant token cannot be replayed
    # as an admin token because the signature wouldn't verify against this key.
    admin_secret_key: str = "dev-admin-secret-change-me"
    admin_access_token_expire_minutes: int = 60

    database_url: str = "postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:5173"

    # --- gateway (Phase 4) ---
    # Seconds to wait on the tenant's upstream before returning 504.
    upstream_timeout_seconds: float = 30.0
    # When Redis is unreachable: allow the request through (fail-open, availability)
    # vs. reject with 503 (fail-closed, protects backends). Default fail-open.
    rate_limit_fail_open: bool = True
    # Trust X-Forwarded-For for the client IP. Off means use the socket peer.
    # Only turn on behind a proxy that overwrites the header (a raw client can spoof it).
    trust_forwarded_for: bool = True

    # --- hardening (Phase 7) ---
    environment: str = "development"
    log_level: str = "INFO"
    # Structured (JSON) logs — on for containers/production log aggregation,
    # off by default so `uvicorn --reload` output stays human-readable locally.
    log_json: bool = False
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0
    # SSRF guard for tenant-supplied upstream_url: reject loopback/private/link-local
    # targets. Off by default — a local dev/demo upstream is very often loopback
    # (e.g. the test suite's stub servers); turn this on in production.
    block_private_upstreams: bool = False

    # --- deploy (Phase 8) ---
    # Host header allowlist (TrustedHostMiddleware). "*" disables the check;
    # set the deployed domain(s) in production to block Host-header spoofing.
    allowed_hosts: str = "*"

    @field_validator("database_url", mode="after")
    @classmethod
    def _use_async_driver(cls, v: str) -> str:
        # managed-Postgres providers hand you a bare `postgres://` / `postgresql://`
        # URL; SQLAlchemy's async engine needs the driver named explicitly.
        for prefix in ("postgresql+asyncpg://", "postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()] or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
