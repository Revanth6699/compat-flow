"""Add public replies to customer reviews.

Revision ID: 20261120_0013
Revises: 20261119_0012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261120_0013"
down_revision = "20261119_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("comment", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER TABLE review_replies ENABLE ROW LEVEL SECURITY")
    op.create_index(
        "ix_review_replies_review_created",
        "review_replies",
        ["review_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_replies_review_created", table_name="review_replies")
    op.drop_table("review_replies")
