from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
