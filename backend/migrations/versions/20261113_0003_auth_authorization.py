"""Add Supabase identity mapping and invitation/permission records.

Revision ID: 20261113_0003
Revises: b58c792979c7
"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261113_0003"
down_revision = "b58c792979c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("uq_users_auth_user_id", "users", ["auth_user_id"], unique=True)
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('owner', 'admin', 'member', 'viewer')",
    )
    op.create_table(
        "user_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'member', 'viewer')", name="ck_invitation_role"),
    )
    op.create_index("ix_user_invitations_org_email", "user_invitations", ["organization_id", "email"])
    role_permissions = op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("permission", sa.String(100), nullable=False),
        sa.UniqueConstraint("role", "permission", name="uq_role_permission"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="ck_role_permissions_role"),
    )
    permission_rows = []
    grants = {
        "owner": ["catalog:read", "catalog:write", "supplier:read", "supplier:write"],
        "admin": ["catalog:read", "catalog:write", "supplier:read", "supplier:write"],
        "member": ["catalog:read", "catalog:write", "supplier:read", "supplier:write"],
        "viewer": ["catalog:read", "supplier:read"],
    }
    for role, permissions in grants.items():
        for permission in permissions:
            permission_rows.append({"id": uuid4(), "role": role, "permission": permission})
    op.bulk_insert(role_permissions, permission_rows)


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_index("ix_user_invitations_org_email", table_name="user_invitations")
    op.drop_table("user_invitations")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_index("uq_users_auth_user_id", table_name="users")
    op.drop_column("users", "auth_user_id")
