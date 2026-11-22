"""Provision private object storage for durable import uploads.

Revision ID: 20261122_0015
Revises: 20261121_0014
"""
from alembic import op
import sqlalchemy as sa


revision = "20261122_0015"
down_revision = "20261121_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Private bucket: only the backend's service credential may access objects.
    # Keep the bucket ceiling at the maximum supported commercial plan size.
    op.execute(
        sa.text(
            """
            INSERT INTO storage.buckets
                (id, name, public, file_size_limit, allowed_mime_types)
            VALUES
                (
                    'compatflow-imports',
                    'compatflow-imports',
                    false,
                    104857600,
                    ARRAY[
                        'text/csv',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'application/json',
                        'application/xml',
                        'text/xml'
                    ]::text[]
                )
            ON CONFLICT (id) DO UPDATE SET
                public = false,
                file_size_limit = 104857600,
                allowed_mime_types = EXCLUDED.allowed_mime_types
            """
        )
    )


def downgrade() -> None:
    # Intentionally retain the bucket and its objects. Removing user uploads
    # during a schema rollback would be destructive.
    pass
