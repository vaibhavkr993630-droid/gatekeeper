from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequestLog(Base):
    """One row per request that reached the rate-limit stage of the gateway
    (allowed or blocked). Feeds the tenant live feed + usage charts (Phase 5)
    and the admin ops view (Phase 6).

    `tenant_id` is denormalised from the service so the tenant-scoped feed query
    never has to join. Short retention — a cleanup job lands in Phase 7; this is
    not a log warehouse.
    """

    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    # which algorithm made the allow/block call, for "which rule triggered" in the feed
    rule_algorithm: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # upstream time-to-first-byte in ms; null for blocked or failed-upstream requests
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
