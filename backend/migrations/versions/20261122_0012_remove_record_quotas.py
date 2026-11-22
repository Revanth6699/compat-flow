"""Remove customer-facing record-count entitlements.

Revision ID: 20261122_0012
Revises: 20261121_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_0012"
down_revision = "20261121_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # File-size entitlements remain plan-specific. Record processing is governed
    # by one system-level safety ceiling, not commercial plan quotas.
    op.execute(
        sa.text(
            "UPDATE subscription_plans "
            "SET entitlements = entitlements - 'upload_max_records'"
        )
    )


def downgrade() -> None:
    # Do not recreate tier-specific record quotas on rollback. The previous
    # values are intentionally not restored because they are no longer policy.
    pass
