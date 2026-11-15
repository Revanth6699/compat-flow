"""Replace the legacy owner role with the single organization admin role.

Revision ID: 20261115_0011
Revises: 20261115_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20261115_0011"
down_revision = "20261115_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate grants before converting legacy owner grants to admin.
    op.drop_constraint("ck_role_permissions_role", "role_permissions", type_="check")
    op.execute(sa.text("DELETE FROM role_permissions WHERE role = 'owner'"))
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'owner'"))
    op.create_check_constraint(
        "ck_role_permissions_role",
        "role_permissions",
        "role IN ('admin', 'member', 'viewer')",
    )
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'member', 'viewer')",
    )


def downgrade() -> None:
    # Preserve admin assignments; recreating a distinct owner role would
    # reintroduce the two-role authorization model this migration removes.
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('owner', 'admin', 'member', 'viewer')",
    )
    op.drop_constraint("ck_role_permissions_role", "role_permissions", type_="check")
    op.create_check_constraint(
        "ck_role_permissions_role",
        "role_permissions",
        "role IN ('owner', 'admin', 'member', 'viewer')",
    )
