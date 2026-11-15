"""Add purpose-specific consent events and data-rights request intake.

Revision ID: 20261115_0011
Revises: 20261115_0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261115_0011"
down_revision = "20261115_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "privacy_consent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("notice_version", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose IN ('service_processing', 'product_updates', 'ai_mapping')", name="ck_privacy_consent_purpose"),
    )
    op.create_index("ix_privacy_consent_events_email", "privacy_consent_events", ["email"])
    op.create_index("ix_privacy_consent_email_purpose_time", "privacy_consent_events", ["email", "purpose", "recorded_at"])
    op.create_table(
        "data_rights_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="received", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("request_type IN ('access', 'correction', 'erasure', 'withdraw_consent', 'grievance')", name="ck_data_rights_request_type"),
        sa.CheckConstraint("status IN ('received', 'identity_verification', 'in_review', 'completed', 'rejected')", name="ck_data_rights_request_status"),
    )
    op.create_index("ix_data_rights_requests_email_created", "data_rights_requests", ["email", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_rights_requests_email_created", table_name="data_rights_requests")
    op.drop_table("data_rights_requests")
    op.drop_index("ix_privacy_consent_email_purpose_time", table_name="privacy_consent_events")
    op.drop_index("ix_privacy_consent_events_email", table_name="privacy_consent_events")
    op.drop_table("privacy_consent_events")
