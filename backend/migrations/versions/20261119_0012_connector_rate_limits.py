"""Add PostgreSQL-backed connector rate-limit counters.

Revision ID: 20261119_0012
Revises: 20261116_0011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261119_0012"
down_revision = "20261116_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_rate_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "window_start",
            name="uq_connector_rate_limits_org_window",
        ),
    )
    op.create_index(
        "ix_connector_rate_limits_window_start",
        "connector_rate_limits",
        ["window_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_connector_rate_limits_window_start",
        table_name="connector_rate_limits",
    )
    op.drop_table("connector_rate_limits")
