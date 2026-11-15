"""Add import record lineage and source locations.

Revision ID: 20261114_0007
Revises: 20261114_0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261114_0007"
down_revision = "20261114_0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("import_row_errors", sa.Column("source_location", sa.String(512), nullable=True))
    op.create_table(
        "import_record_lineage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(40), nullable=False),
        sa.Column("source_location", sa.String(512), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=True),
        sa.Column("target_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("job_id", "source_location", name="uq_import_lineage_job_location"),
    )
    op.create_index("ix_import_lineage_org_job", "import_record_lineage", ["organization_id", "job_id"])

def downgrade() -> None:
    op.drop_index("ix_import_lineage_org_job", table_name="import_record_lineage")
    op.drop_table("import_record_lineage")
    op.drop_column("import_row_errors", "source_location")
