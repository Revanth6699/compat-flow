"""Add demo access request approvals and revocation.

Revision ID: 20261114_0011
Revises: 20261114_0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261114_0011"
down_revision = "20261114_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_access_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("organization", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("reviewed_by", sa.String(length=320)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'revoked', 'rejected')", name="ck_demo_access_status"),
    )
    op.create_index("ix_demo_access_requests_email", "demo_access_requests", ["email"])
    op.create_index("ix_demo_access_email_status", "demo_access_requests", ["email", "status"])


def downgrade() -> None:
    op.drop_index("ix_demo_access_email_status", table_name="demo_access_requests")
    op.drop_index("ix_demo_access_requests_email", table_name="demo_access_requests")
    op.drop_table("demo_access_requests")
