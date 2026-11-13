"""Add account classification and subscription/payment records.

Revision ID: 20261113_0004
Revises: 20261113_0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261113_0004"
down_revision = "20261113_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_type", sa.String(length=20), nullable=False, server_default="demo"),
    )
    op.create_check_constraint(
        "ck_users_account_type",
        "users",
        "account_type IN ('demo', 'subscriber', 'enterprise')",
    )

    op.create_table(
        "subscription_plans",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("monthly_price_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("storage_limit_bytes", sa.BigInteger(), nullable=True),
        sa.Column("monthly_validation_limit", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("monthly_price_minor", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(plans, [
        {"code": "starter", "name": "Starter", "monthly_price_minor": 2700, "currency": "USD", "is_active": True},
        {"code": "growth", "name": "Growth", "monthly_price_minor": 6400, "currency": "USD", "is_active": True},
        {"code": "business", "name": "Business", "monthly_price_minor": 15300, "currency": "USD", "is_active": True},
        {"code": "enterprise", "name": "Enterprise", "monthly_price_minor": None, "currency": "USD", "is_active": True},
    ])

    op.add_column("subscription_plans", sa.Column("entitlements", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    entitlements = sa.table("subscription_plans", sa.column("code", sa.String), sa.column("entitlements", postgresql.JSONB))
    op.execute(entitlements.update().where(entitlements.c.code == "starter").values(entitlements={"csv_validation": True, "validation_metrics": True, "issue_reports": True}))
    op.execute(entitlements.update().where(entitlements.c.code == "growth").values(entitlements={"csv_validation": True, "validation_metrics": True, "issue_reports": True, "supplier_catalogs": True, "version_comparison": True, "custom_rules": True, "recurring_validation": True}))
    op.execute(entitlements.update().where(entitlements.c.code == "business").values(entitlements={"csv_validation": True, "validation_metrics": True, "issue_reports": True, "supplier_catalogs": True, "version_comparison": True, "custom_rules": True, "recurring_validation": True, "team_review": True, "issue_assignment": True, "approval_workflows": True, "audit_history": True, "exports": True, "integrations": True}))
    op.execute(entitlements.update().where(entitlements.c.code == "enterprise").values(entitlements={"csv_validation": True, "validation_metrics": True, "issue_reports": True, "supplier_catalogs": True, "version_comparison": True, "custom_rules": True, "recurring_validation": True, "team_review": True, "issue_assignment": True, "approval_workflows": True, "audit_history": True, "exports": True, "integrations": True, "custom_limits": True, "governance": True, "custom_support_sla": True}))

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("subscription_plans.code"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("billing_interval", sa.String(16), nullable=False, server_default="month"),
        sa.Column("provider", sa.String(32)),
        sa.Column("provider_customer_id", sa.String(160)),
        sa.Column("provider_subscription_id", sa.String(160), unique=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("canceled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','trialing','active','past_due','canceled','expired','incomplete')", name="ck_subscriptions_status"),
        sa.CheckConstraint("billing_interval IN ('month','year')", name="ck_subscriptions_interval"),
    )
    op.create_index("uq_subscriptions_one_current_per_org", "subscriptions", ["organization_id"], unique=True, postgresql_where=sa.text("status IN ('active', 'trialing')"))
    op.create_index("ix_subscriptions_org_status", "subscriptions", ["organization_id", "status"])
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_payment_id", sa.String(160)),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("payment_method_type", sa.String(32)),
        sa.Column("receipt_url", sa.String(512)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_payments_provider_payment"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_payments_nonnegative_amount"),
        sa.CheckConstraint("status IN ('pending','succeeded','failed','refunded','partially_refunded','voided')", name="ck_payments_status"),
    )
    op.create_index("ix_payments_org_created", "payments", ["organization_id", "created_at"])
    op.create_index("ix_payments_subscription", "payments", ["subscription_id"])

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(180), nullable=False, unique=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("processing_status", sa.String(24), nullable=False, server_default="received"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("processing_status IN ('received','processing','processed','failed')", name="ck_payment_webhook_status"),
    )


def downgrade() -> None:
    op.drop_table("payment_webhook_events")
    op.drop_index("ix_payments_subscription", table_name="payments")
    op.drop_index("ix_payments_org_created", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_subscriptions_user_status", table_name="subscriptions")
    op.drop_index("uq_subscriptions_one_current_per_org", table_name="subscriptions")
    op.drop_index("ix_subscriptions_org_status", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
    op.drop_constraint("ck_users_account_type", "users", type_="check")
    op.drop_column("users", "account_type")
