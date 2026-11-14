"""Add typed product identifier registry.

Revision ID: 20261114_0006
Revises: 20261114_0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261114_0006"
down_revision = "20261114_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier_type", sa.String(32), nullable=False),
        sa.Column("namespace", sa.String(80), nullable=False, server_default="global"),
        sa.Column("value", sa.String(160), nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "product_id"], ["products.organization_id", "products.id"], name="fk_product_identifiers_org_product"),
        sa.UniqueConstraint("organization_id", "identifier_type", "namespace", "value", name="uq_product_identifiers_org_type_namespace_value"),
        sa.CheckConstraint(
            "identifier_type IN ('upc', 'ean', 'gtin', 'asin', 'marketplace_id', 'manufacturer_code', 'source_product_id', 'other')",
            name="ck_product_identifiers_type",
        ),
    )
    op.create_index("ix_product_identifiers_org_product", "product_identifiers", ["organization_id", "product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_identifiers_org_product", table_name="product_identifiers")
    op.drop_table("product_identifiers")
