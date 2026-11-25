"""Merge production validation-profile history with staged tenant RLS history.

Revision ID: 20261126_0015
Revises: 20261122_0013, 20261125_0014
"""
revision = "20261126_0015"
down_revision = ("20261122_0013", "20261125_0014")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The two parents contain the independent mainline schema and staged RLS rollout.
    pass


def downgrade() -> None:
    # Alembic merge points are intentionally non-reversible; downgrade through parents.
    pass
