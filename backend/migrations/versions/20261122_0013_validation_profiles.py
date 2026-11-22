"""Add organization-scoped reusable validation profiles and rules.

Revision ID: 20261122_0013
Revises: 20261122_0012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261122_0013"
down_revision = "20261122_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("dataset_type", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_validation_profiles_org_creator",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_validation_profiles_org_id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_validation_profiles_org_name"),
    )
    op.create_index(
        "ix_validation_profiles_org_dataset",
        "validation_profiles",
        ["organization_id", "dataset_type"],
    )

    op.create_table(
        "validation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("severity", sa.String(length=16), server_default="warning", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "profile_id"],
            ["validation_profiles.organization_id", "validation_profiles.id"],
            name="fk_validation_rules_org_profile",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "code", name="uq_validation_rules_profile_code"),
        sa.CheckConstraint(
            "rule_type IN ('required', 'unique', 'numeric_min', 'numeric_max', 'allowed_values', 'min_length', 'max_length')",
            name="ck_validation_rules_type",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'warning', 'info')",
            name="ck_validation_rules_severity",
        ),
    )
    op.create_index(
        "ix_validation_rules_org_profile_enabled",
        "validation_rules",
        ["organization_id", "profile_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_validation_rules_org_profile_enabled", table_name="validation_rules")
    op.drop_table("validation_rules")
    op.drop_index("ix_validation_profiles_org_dataset", table_name="validation_profiles")
    op.drop_table("validation_profiles")
