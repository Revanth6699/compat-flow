"""Add tenant-scoped encrypted connector configurations.

Revision ID: 20261119_0010
Revises: 20261115_0009
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261119_0010"
down_revision = "20261115_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_descriptor", sa.String(length=512), nullable=False),
        sa.Column(
            "source_settings", postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column(
            "encryption_key_version", sa.String(length=16),
            server_default="v1", nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_type IN ('rest_api', 'sftp', 'sql_server')",
            name="ck_connector_configurations_source_type",
        ),
    )
    op.create_index(
        "ix_connector_configurations_org_source",
        "connector_configurations", ["organization_id", "source_type"],
    )
    op.create_index(
        "uq_connector_configurations_org_name_active",
        "connector_configurations", ["organization_id", "name"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_connector_configurations_org_name_active",
        table_name="connector_configurations",
    )
    op.drop_index(
        "ix_connector_configurations_org_source",
        table_name="connector_configurations",
    )
    op.drop_table("connector_configurations")
