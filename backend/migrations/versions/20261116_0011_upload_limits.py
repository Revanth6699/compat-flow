"""Configure per-file upload limits for paid subscription tiers.

Revision ID: 20261116_0011
Revises: 20261115_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20261116_0011"
down_revision = "20261115_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("entitlements", sa.JSON),
    )
    bind = op.get_bind()
    limits = {
        "starter": {"upload_max_records": 20_000, "upload_max_bytes": 10 * 1024 * 1024},
        "growth": {"upload_max_records": 40_000, "upload_max_bytes": 20 * 1024 * 1024},
        "business": {"upload_max_records": 100_000, "upload_max_bytes": 100 * 1024 * 1024},
    }
    for code, values in limits.items():
        bind.execute(
            plans.update()
            .where(plans.c.code == code)
            .values(entitlements=sa.text(
                "entitlements || '" + __import__("json").dumps(values) + "'::jsonb"
            ))
        )
    # Enterprise upload limits are intentionally not assigned a default.
    # Configure upload_max_records and upload_max_bytes on the enterprise plan
    # for the agreed customer contract; the API fails closed until configured.


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE subscription_plans SET entitlements = "
            "entitlements - 'upload_max_records' - 'upload_max_bytes'"
        )
    )
