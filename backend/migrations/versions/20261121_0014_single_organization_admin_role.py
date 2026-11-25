"""Replace the legacy owner role with the single organization admin role.

Revision ID: 20261121_0014
Revises: 20261120_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20261121_0014"
down_revision = "20261120_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration may run after tenant RLS has already been enabled on staging.
    op.execute("SELECT set_config('app.is_platform_admin', 'true', true)")
    op.drop_constraint("ck_role_permissions_role", "role_permissions", type_="check")
    op.execute(sa.text("DELETE FROM role_permissions WHERE role = 'owner'"))
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'owner'"))
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'member', 'viewer')")
    op.create_check_constraint(
        "ck_role_permissions_role", "role_permissions", "role IN ('admin', 'member', 'viewer')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_role_permissions_role", "role_permissions", type_="check")
    op.create_check_constraint(
        "ck_role_permissions_role", "role_permissions", "role IN ('owner', 'admin', 'member', 'viewer')"
    )
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('owner', 'admin', 'member', 'viewer')"
    )
