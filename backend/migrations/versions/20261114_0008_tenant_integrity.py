"""Enforce organization ownership across billing, invitations, and import lineage.

Revision ID: 20261114_0008
Revises: 20261114_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20261114_0008"
down_revision = "20261114_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    invalid_links = {
        "user_invitations -> inviter": """
            SELECT COUNT(*) FROM user_invitations i
            JOIN users u ON u.id = i.invited_by_user_id
            WHERE i.invited_by_user_id IS NOT NULL
              AND i.organization_id <> u.organization_id
        """,
        "subscriptions -> user": """
            SELECT COUNT(*) FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.organization_id <> u.organization_id
        """,
        "payments -> user": """
            SELECT COUNT(*) FROM payments p
            JOIN users u ON u.id = p.user_id
            WHERE p.organization_id <> u.organization_id
        """,
        "payments -> subscription": """
            SELECT COUNT(*) FROM payments p
            JOIN subscriptions s ON s.id = p.subscription_id
            WHERE p.subscription_id IS NOT NULL
              AND p.organization_id <> s.organization_id
        """,
        "import_record_lineage -> import_job": """
            SELECT COUNT(*) FROM import_record_lineage l
            JOIN import_jobs j ON j.id = l.job_id
            WHERE l.organization_id <> j.organization_id
        """,
    }
    for relation, query in invalid_links.items():
        if bind.execute(sa.text(query)).scalar_one():
            raise RuntimeError(
                f"Cannot enable tenant constraints: existing cross-organization links in {relation}."
            )

    op.create_unique_constraint("uq_users_org_id", "users", ["organization_id", "id"])
    op.create_unique_constraint("uq_import_jobs_org_id", "import_jobs", ["organization_id", "id"])
    op.create_unique_constraint("uq_subscriptions_org_id", "subscriptions", ["organization_id", "id"])

    op.create_foreign_key(
        "fk_user_invitations_org_inviter", "user_invitations", "users",
        ["organization_id", "invited_by_user_id"], ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_subscriptions_org_user", "subscriptions", "users",
        ["organization_id", "user_id"], ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_payments_org_user", "payments", "users",
        ["organization_id", "user_id"], ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_payments_org_subscription", "payments", "subscriptions",
        ["organization_id", "subscription_id"], ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_import_lineage_org_job", "import_record_lineage", "import_jobs",
        ["organization_id", "job_id"], ["organization_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_import_lineage_org_job", "import_record_lineage", type_="foreignkey")
    op.drop_constraint("fk_payments_org_subscription", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_org_user", "payments", type_="foreignkey")
    op.drop_constraint("fk_subscriptions_org_user", "subscriptions", type_="foreignkey")
    op.drop_constraint("fk_user_invitations_org_inviter", "user_invitations", type_="foreignkey")
    op.drop_constraint("uq_subscriptions_org_id", "subscriptions", type_="unique")
    op.drop_constraint("uq_import_jobs_org_id", "import_jobs", type_="unique")
    op.drop_constraint("uq_users_org_id", "users", type_="unique")
