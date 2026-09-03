"""request_logs

Revision ID: 0003_request_logs
Revises: 0002_services
Create Date: 2026-09-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_request_logs"
down_revision: str | None = "0002_services"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=False),
        sa.Column("rule_algorithm", sa.String(length=40), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_request_logs_tenant_id", "request_logs", ["tenant_id"])
    op.create_index("ix_request_logs_service_id", "request_logs", ["service_id"])
    op.create_index("ix_request_logs_created_at", "request_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("request_logs")
