"""Enable forced tenant RLS for the staging application schema.

Revision ID: 20261125_0014
Revises: 20261120_0013

The application connects with a verified Supabase subject and a tenant ID
resolved from the CompatFlow user record. Policies consume only transaction-
local settings populated by app.core.database. This migration is intended for
the isolated staging database first; production needs its own restricted login
role and credential cutover before this migration is promoted.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261125_0014"
down_revision = "20261120_0013"
branch_labels = None
depends_on = None

ADMIN = "COALESCE(current_setting('app.is_platform_admin', true) = 'true', false)"
WEBHOOK = "COALESCE(current_setting('app.verified_payment_webhook', true) = 'true', false)"
ORG = "NULLIF(current_setting('app.organization_id', true), '')::uuid"
AUTH_USER = "NULLIF(current_setting('app.auth_user_id', true), '')::uuid"
EMAIL = "lower(NULLIF(current_setting('app.user_email', true), ''))"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names(schema="public"))

    # Organizations and users need bootstrap/onboarding policies distinct
    # from the normal tenant policy.
    if "organizations" in tables:
        op.execute("ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY organizations_tenant_access ON public.organizations
            FOR ALL USING (id = {ORG} OR {ADMIN})
            WITH CHECK (id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY organizations_onboarding_insert ON public.organizations
            FOR INSERT WITH CHECK (
                COALESCE(current_setting('app.allow_onboarding', true) = 'true', false)
                AND {AUTH_USER} IS NOT NULL
            )"""
        )

    if "users" in tables:
        op.execute("ALTER TABLE public.users ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.users FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY users_self_or_tenant_select ON public.users
            FOR SELECT USING (auth_user_id = {AUTH_USER} OR organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY users_tenant_write ON public.users
            FOR UPDATE USING (organization_id = {ORG} OR {ADMIN})
            WITH CHECK (organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY users_tenant_delete ON public.users
            FOR DELETE USING (organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY users_onboarding_insert ON public.users
            FOR INSERT WITH CHECK (
                COALESCE(current_setting('app.allow_onboarding', true) = 'true', false)
                AND auth_user_id = {AUTH_USER}
                AND organization_id = {ORG}
            )"""
        )
        op.execute(
            f"""CREATE POLICY users_tenant_insert ON public.users
            FOR INSERT WITH CHECK (organization_id = {ORG} OR {ADMIN})"""
        )

    # Every organization_id table gets a uniform tenant boundary. The webhook
    # bypass is set only after the Razorpay signature has been verified.
    excluded = {
        "alembic_version", "organizations", "users", "reviews",
        "import_row_errors", "review_replies",
    }
    inspector = sa.inspect(bind)
    for table in sorted(tables - excluded):
        columns = {column["name"] for column in inspector.get_columns(table, schema="public")}
        if "organization_id" not in columns:
            continue
        qualified = f'public."{table}"'
        op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY "{table}_tenant_isolation" ON {qualified}
            FOR ALL USING (organization_id = {ORG} OR {ADMIN} OR {WEBHOOK})
            WITH CHECK (organization_id = {ORG} OR {ADMIN} OR {WEBHOOK})"""
        )

    if "reviews" in tables:
        op.execute("ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.reviews FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY reviews_public_published_read ON public.reviews
            FOR SELECT USING (is_published IS TRUE OR organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY reviews_tenant_write ON public.reviews
            FOR INSERT WITH CHECK (organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY reviews_tenant_update ON public.reviews
            FOR UPDATE USING (organization_id = {ORG} OR {ADMIN})
            WITH CHECK (organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY reviews_tenant_delete ON public.reviews
            FOR DELETE USING (organization_id = {ORG} OR {ADMIN})"""
        )

    if "import_row_errors" in tables:
        op.execute("ALTER TABLE public.import_row_errors ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.import_row_errors FORCE ROW LEVEL SECURITY")
        parent_access = f"""EXISTS (
            SELECT 1 FROM public.import_jobs j
            WHERE j.id = import_row_errors.job_id
              AND (j.organization_id = {ORG} OR {ADMIN} OR {WEBHOOK})
        )"""
        op.execute(
            f"""CREATE POLICY import_row_errors_parent_tenant ON public.import_row_errors
            FOR ALL USING ({parent_access}) WITH CHECK ({parent_access})"""
        )

    if "review_replies" in tables:
        op.execute("ALTER TABLE public.review_replies ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.review_replies FORCE ROW LEVEL SECURITY")
        review_access = f"""EXISTS (
            SELECT 1 FROM public.reviews r
            WHERE r.id = review_replies.review_id
              AND (r.organization_id = {ORG} OR {ADMIN})
        )"""
        op.execute(
            f"""CREATE POLICY review_replies_public_or_tenant_read ON public.review_replies
            FOR SELECT USING (
                EXISTS (
                    SELECT 1 FROM public.reviews r
                    WHERE r.id = review_replies.review_id
                      AND (r.is_published IS TRUE OR r.organization_id = {ORG} OR {ADMIN})
                )
            )"""
        )
        op.execute(
            f"""CREATE POLICY review_replies_tenant_write ON public.review_replies
            FOR INSERT WITH CHECK ({review_access})"""
        )
        op.execute(
            f"""CREATE POLICY review_replies_tenant_update ON public.review_replies
            FOR UPDATE USING ({review_access}) WITH CHECK ({review_access})"""
        )
        op.execute(
            f"""CREATE POLICY review_replies_tenant_delete ON public.review_replies
            FOR DELETE USING ({review_access})"""
        )

    if "demo_access_requests" in tables:
        op.execute("ALTER TABLE public.demo_access_requests ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.demo_access_requests FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY demo_requests_self_or_admin_read ON public.demo_access_requests
            FOR SELECT USING (email = {EMAIL} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY demo_requests_public_insert ON public.demo_access_requests
            FOR INSERT WITH CHECK (
                COALESCE(current_setting('app.allow_demo_request_insert', true) = 'true', false)
                AND email = {EMAIL}
            )"""
        )
        op.execute(
            f"""CREATE POLICY demo_requests_admin_update ON public.demo_access_requests
            FOR UPDATE USING ({ADMIN}) WITH CHECK ({ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY demo_requests_admin_delete ON public.demo_access_requests
            FOR DELETE USING ({ADMIN})"""
        )

    if "user_invitations" in tables:
        op.execute(
            f"""CREATE POLICY user_invitations_invitee_read ON public.user_invitations
            FOR SELECT USING (lower(email) = {EMAIL} OR organization_id = {ORG} OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY user_invitations_invitee_accept ON public.user_invitations
            FOR UPDATE USING (lower(email) = {EMAIL} OR organization_id = {ORG} OR {ADMIN})
            WITH CHECK (lower(email) = {EMAIL} OR organization_id = {ORG} OR {ADMIN})"""
        )

    if "subscription_plans" in tables:
        op.execute("ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.subscription_plans FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY subscription_plans_authenticated_read ON public.subscription_plans
            FOR SELECT USING ({AUTH_USER} IS NOT NULL OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY subscription_plans_admin_write ON public.subscription_plans
            FOR ALL USING ({ADMIN}) WITH CHECK ({ADMIN})"""
        )

    if "role_permissions" in tables:
        op.execute("ALTER TABLE public.role_permissions ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.role_permissions FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY role_permissions_authenticated_read ON public.role_permissions
            FOR SELECT USING ({AUTH_USER} IS NOT NULL OR {ADMIN})"""
        )
        op.execute(
            f"""CREATE POLICY role_permissions_admin_write ON public.role_permissions
            FOR ALL USING ({ADMIN}) WITH CHECK ({ADMIN})"""
        )

    if "payment_webhook_events" in tables:
        op.execute("ALTER TABLE public.payment_webhook_events ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.payment_webhook_events FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY payment_webhook_verified_or_admin ON public.payment_webhook_events
            FOR ALL USING ({WEBHOOK} OR {ADMIN}) WITH CHECK ({WEBHOOK} OR {ADMIN})"""
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names(schema="public"))
    for table in sorted(tables):
        if table == "alembic_version":
            continue
        qualified = f'public."{table}"'
        op.execute(f"ALTER TABLE {qualified} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified} DISABLE ROW LEVEL SECURITY")
        policies = bind.execute(
            sa.text(
                "SELECT policyname FROM pg_policies "
                "WHERE schemaname='public' AND tablename=:table_name"
            ),
            {"table_name": table},
        ).scalars().all()
        for policy in policies:
            op.execute(f' DROP POLICY IF EXISTS "{policy}" ON {qualified}')
