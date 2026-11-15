"""Set organization member-seat entitlements by subscription plan.

Revision ID: 20261114_0009
Revises: 20261114_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20261114_0009"
down_revision = "20261114_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("entitlements", sa.JSON),
    )
    bind = op.get_bind()
    bind.execute(
        plans.update()
        .where(plans.c.code == "starter")
        .values(entitlements=sa.text("entitlements || '{\"member_seats\": 3}'::jsonb"))
    )
    bind.execute(
        plans.update()
        .where(plans.c.code == "growth")
        .values(entitlements=sa.text("entitlements || '{\"member_seats\": 10}'::jsonb"))
    )
    bind.execute(
        plans.update()
        .where(plans.c.code == "business")
        .values(entitlements=sa.text("entitlements || '{\"member_seats\": 25}'::jsonb"))
    )
    bind.execute(
        plans.update()
        .where(plans.c.code == "enterprise")
        .values(entitlements=sa.text("entitlements || '{\"member_seats\": null}'::jsonb"))
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE subscription_plans SET entitlements = entitlements - 'member_seats'"
        )
    )
