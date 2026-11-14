"""Separate product variants, supplier offers, and inventory snapshots.

Revision ID: 20261114_0005
Revises: 20261113_0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261114_0005"
down_revision = "20261113_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_sku", sa.String(100), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "product_id"], ["products.organization_id", "products.id"], name="fk_product_variants_org_product"),
        sa.UniqueConstraint("organization_id", "variant_sku", name="uq_product_variants_org_sku"),
    )
    op.create_index("ix_product_variants_org_product", "product_variants", ["organization_id", "product_id"])

    op.create_table(
        "supplier_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supplier_sku", sa.String(120), nullable=True),
        sa.Column("supplier_product_id", sa.String(160), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("unit_of_measure", sa.String(40), nullable=True),
        sa.Column("minimum_order_quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "supplier_id"], ["suppliers.organization_id", "suppliers.id"], name="fk_supplier_offers_org_supplier"),
        sa.ForeignKeyConstraint(["organization_id", "product_id"], ["products.organization_id", "products.id"], name="fk_supplier_offers_org_product"),
        sa.UniqueConstraint("organization_id", "supplier_id", "supplier_sku", name="uq_supplier_offers_org_supplier_sku"),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_supplier_offers_price_nonnegative"),
        sa.CheckConstraint("minimum_order_quantity IS NULL OR minimum_order_quantity > 0", name="ck_supplier_offers_moq_positive"),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="ck_supplier_offers_lead_time_nonnegative"),
    )
    op.create_index("ix_supplier_offers_org_product", "supplier_offers", ["organization_id", "product_id"])
    op.create_index("ix_supplier_offers_org_supplier", "supplier_offers", ["organization_id", "supplier_id"])

    op.create_table(
        "inventory_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("warehouse_code", sa.String(120), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(18, 4), nullable=True),
        sa.Column("quantity_reserved", sa.Numeric(18, 4), nullable=True),
        sa.Column("quantity_available", sa.Numeric(18, 4), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "product_id"], ["products.organization_id", "products.id"], name="fk_inventory_snapshots_org_product"),
        sa.ForeignKeyConstraint(["organization_id", "supplier_offer_id"], ["supplier_offers.organization_id", "supplier_offers.id"], name="fk_inventory_snapshots_org_offer"),
        sa.CheckConstraint("quantity_on_hand IS NULL OR quantity_on_hand >= 0", name="ck_inventory_on_hand_nonnegative"),
        sa.CheckConstraint("quantity_reserved IS NULL OR quantity_reserved >= 0", name="ck_inventory_reserved_nonnegative"),
        sa.CheckConstraint("quantity_available IS NULL OR quantity_available >= 0", name="ck_inventory_available_nonnegative"),
    )
    op.create_index("ix_inventory_snapshots_org_product_time", "inventory_snapshots", ["organization_id", "product_id", "snapshot_at"])
    op.create_index("ix_inventory_snapshots_org_warehouse_time", "inventory_snapshots", ["organization_id", "warehouse_code", "snapshot_at"])


def downgrade() -> None:
    op.drop_index("ix_inventory_snapshots_org_warehouse_time", table_name="inventory_snapshots")
    op.drop_index("ix_inventory_snapshots_org_product_time", table_name="inventory_snapshots")
    op.drop_table("inventory_snapshots")
    op.drop_index("ix_supplier_offers_org_supplier", table_name="supplier_offers")
    op.drop_index("ix_supplier_offers_org_product", table_name="supplier_offers")
    op.drop_table("supplier_offers")
    op.drop_index("ix_product_variants_org_product", table_name="product_variants")
    op.drop_table("product_variants")
