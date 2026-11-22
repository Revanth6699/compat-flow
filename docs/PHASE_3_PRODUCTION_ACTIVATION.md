# Phase 3 production activation checklist

This checklist separates repository work from operator-only activation. A feature is not considered production-ready merely because its code exists.

## Production database migrations

The production migration workflow is intentionally manual and requires two explicit confirmations:

1. Create a recoverable backup of the actual production PostgreSQL database. Verify that the backup is usable; a backup job reporting success is not sufficient.
2. Configure the GitHub Actions environment named `production` and add the environment secret `PRODUCTION_DATABASE_URL` for the production database only.
3. Review the migration head shown by the workflow against the release commit.
4. Run **Apply production database migration** with `backup_verified=yes` and the exact confirmation text `APPLY PRODUCTION MIGRATIONS`.
5. Confirm the resulting Alembic revision is the expected head and perform authenticated smoke tests.

Do not reuse `STAGING_DATABASE_URL`. Do not copy production database credentials into workflow logs, issues, or chat.

The current migration chain includes the review-replies table migration (`20261120_0013`) and validation-profile migrations. The production API previously logged an undefined-table error for `review_replies`; verify this table exists after migration.

## Release checks still required

- Confirm the production database target and Alembic revision.
- Verify the public reviews/replies read path and platform-admin-only reply write path.
- Submit a contact form and verify both the Supabase record and Gmail notification; a saved form does not prove email delivery.
- Submit a demo request and verify the backend request queue, Supabase `contact_requests` mirror, approval/revocation state, and Gmail notification independently.
- Verify subscription lifecycle using Razorpay test mode, including webhook signature verification, duplicate event handling, renewals, failed payments, cancellation, and entitlement expiry.
- Verify REST API, SFTP, and SQL Server against real supplier endpoints before enabling customer connections. Mock tests are not production connectivity evidence.
- Verify the import worker and Redis are provisioned, share the correct database/storage configuration, and complete a health-check task before enabling durable job submission.
- Verify backup restoration and operational alerting.

## Known implementation boundaries

- REST pagination is currently explicit page-number pagination; cursor/link pagination requires supplier-specific adapters.
- The compatibility Celery task still parses CSV into memory. It is not a bounded-memory multi-format import pipeline.
- Invitation links do not yet have automated invitation email delivery.
- Razorpay live credentials, provider plans, webhook delivery, and a real payment have not been verified.
- Connector credentials are request-scoped; there is no reusable credential vault.
- Refund initiation and reconciliation are not exposed as customer-facing APIs.

Do not describe these capabilities as fully production-enabled until the corresponding release checks pass.
