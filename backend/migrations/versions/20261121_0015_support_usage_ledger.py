"""Add complaint tracking and subscription usage ledger.

Revision ID: 20261121_0015
Revises: 20261121_0014
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261121_0015"
down_revision = "20261121_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_complaints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("requester_name", sa.String(120), nullable=False),
        sa.Column("requester_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("admin_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'resolved', 'closed')", name="ck_support_complaints_status"),
    )
    op.create_index("ix_support_complaints_status_created", "support_complaints", ["status", "created_at"])
    op.create_table(
        "subscription_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("event_type IN ('validation', 'storage')", name="ck_usage_event_type"),
    )
    op.create_index("ix_subscription_usage_org_created", "subscription_usage_events", ["organization_id", "created_at"])


def downgrade():
    op.drop_index("ix_subscription_usage_org_created", table_name="subscription_usage_events")
    op.drop_table("subscription_usage_events")
    op.drop_index("ix_support_complaints_status_created", table_name="support_complaints")
    op.drop_table("support_complaints")
