"""Apply tenant RLS to validation profile tables created on mainline.

Revision ID: 20261126_0016
Revises: 20261126_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20261126_0016"
down_revision = "20261126_0015"
branch_labels = None
depends_on = None

ORG = "NULLIF(current_setting('app.organization_id', true), '')::uuid"
ADMIN = "COALESCE(current_setting('app.is_platform_admin', true) = 'true', false)"
WEBHOOK = "COALESCE(current_setting('app.verified_payment_webhook', true) = 'true', false)"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names(schema="public"))
    for table in ("validation_profiles", "validation_rules"):
        if table not in tables:
            continue
        columns = {c["name"] for c in sa.inspect(bind).get_columns(table, schema="public")}
        if "organization_id" not in columns:
            raise RuntimeError(f"{table} is missing organization_id; refusing to enable unsafe tenant policy")
        qualified = f'public."{table}"'
        op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
        op.execute(
            f'''CREATE POLICY "{table}_tenant_isolation" ON {qualified}
            FOR ALL USING (organization_id = {ORG} OR {ADMIN} OR {WEBHOOK})
            WITH CHECK (organization_id = {ORG} OR {ADMIN} OR {WEBHOOK})'''
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names(schema="public"))
    for table in ("validation_profiles", "validation_rules"):
        if table in tables:
            op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation" ON public."{table}"')
            op.execute(f'ALTER TABLE public."{table}" NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
