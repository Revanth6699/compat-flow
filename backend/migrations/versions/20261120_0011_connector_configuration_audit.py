"""Add immutable audit events for saved connector configuration changes.

Revision ID: 20261120_0011
Revises: 20261119_0010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261120_0011"
down_revision = "20261119_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_configuration_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "configuration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connector_configurations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_descriptor", sa.String(length=512), nullable=False),
        sa.Column("key_version_from", sa.String(length=16), nullable=True),
        sa.Column("key_version_to", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('created', 'deleted', 'credentials_rotated')",
            name="ck_connector_configuration_audit_action",
        ),
    )
    op.create_index(
        "ix_connector_configuration_audit_org_config_created",
        "connector_configuration_audit_events",
        ["organization_id", "configuration_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_connector_configuration_audit_org_config_created",
        table_name="connector_configuration_audit_events",
    )
    op.drop_table("connector_configuration_audit_events")
