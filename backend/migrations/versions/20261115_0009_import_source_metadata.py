"""Store source type and safe connector provenance on import jobs.

Revision ID: 20261115_0009
Revises: 20261114_0008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261115_0009"
down_revision = "20261114_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_jobs",
        sa.Column("source_type", sa.String(length=20), server_default="file", nullable=False),
    )
    op.add_column(
        "import_jobs",
        sa.Column("source_descriptor", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "source_metadata")
    op.drop_column("import_jobs", "source_descriptor")
    op.drop_column("import_jobs", "source_type")
