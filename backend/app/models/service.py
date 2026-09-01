import secrets
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import RateLimitAlgorithm
from app.db.base import Base, TimestampMixin


def _public_id() -> str:
    return secrets.token_hex(12)


class Service(Base, TimestampMixin):
    """A tenant-registered backend + its rate-limit policy.

    Traffic is routed at the gateway via `public_id` (Phase 4); it is opaque and
    safe to expose. `upstream_url` is the tenant's real backend that allowed
    requests get forwarded to.
    """

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, default=_public_id, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    upstream_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rule: Mapped["RateLimitRule"] = relationship(
        back_populates="service", cascade="all, delete-orphan", uselist=False
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )


class RateLimitRule(Base, TimestampMixin):
    """The policy enforced for a service. One per service in v1 — modeled as its own
    row so multiple rules (per-method, per-path) can be added later without a migration
    to the Service table.
    """

    __tablename__ = "rate_limit_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    algorithm: Mapped[RateLimitAlgorithm] = mapped_column(String(40), nullable=False)
    limit: Mapped[int] = mapped_column(Integer, nullable=False)  # requests per window
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # token-bucket capacity / burst allowance; defaults to `limit` when unset
    burst: Mapped[int | None] = mapped_column(Integer, nullable=True)

    service: Mapped[Service] = relationship(back_populates="rule")


class ApiKey(Base, TimestampMixin):
    """Authenticates traffic through the gateway for one service. Only the SHA-256
    hash is stored; the plaintext is returned once at creation time.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    service: Mapped[Service] = relationship(back_populates="api_keys")
