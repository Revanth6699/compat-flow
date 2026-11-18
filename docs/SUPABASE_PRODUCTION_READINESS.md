# Supabase PostgreSQL production-readiness audit

**Branch:** `infra/supabase-production-readiness`  
**Audit source:** GitHub `feature/organization-first-onboarding`  
**Status:** Preparation only. No Supabase schema, data, or Render environment has been changed.

## Decision

Supabase PostgreSQL is a viable candidate for the CompatFlow application database, but production must not be pointed at it until every release gate below is satisfied. The current Render production backend has no `DATABASE_URL`; leave it unset until the explicit go-ahead is given.

## Verified environment facts

- Supabase project `CompatFlow` is active and runs PostgreSQL 17.11 in Seoul.
- A connection test through the Session Pooler succeeded.
- A Supabase public-schema custom-format backup was created on 2026-11-18 and its archive table-of-contents was inspected. This is not yet a proven restore.
- The current public application schema contains `contact_requests` and `demo_access`; both contain existing data and must be preserved.
- The Supabase migration history query returned no recorded migrations. The repository contains a SQL migration for those two tables, so the live schema and migration history need reconciliation rather than blindly reapplying it.
- The backend migration chain on the staging branch currently ends at `20261116_0011_upload_limits`.

## Table ownership — preserve the three demo/contact concepts

These tables are distinct and must not be renamed, merged, or dropped:

| Table | Owner / purpose |
|---|---|
| `contact_requests` | General contact submissions and demo-request history mirrored by the frontend |
| `demo_access` | Approved/revoked demo-access entitlement |
| `demo_access_requests` | Backend queue used by the platform-admin demo-request dashboard |

The demo request route writes the authoritative queue record to `demo_access_requests`; the Supabase mirror is a separate operation. This explains why email delivery, the backend dashboard queue, and Supabase mirror can differ.

## Blocking issues

### 1. Organization roles do not match the product requirement

Current backend code and migrations still support `owner`, `admin`, `member`, and `viewer`. First-user onboarding creates `owner`; invitations accept `admin`, `member`, or `viewer`; only an owner may invite another admin. This conflicts with the product decision of one Organization Admin role and invited employees as Members.

The refactor must cover:
- onboarding role assignment;
- invitation request validation and acceptance;
- member management and authorization dependencies;
- permission seed rows and role check constraints;
- deletion and organization lifecycle behavior;
- frontend role labels and access controls;
- tests and operational documentation.

Do not simply drop the `owner` role constraint: the existing code relies on it for organization deletion and privilege checks. Migrate the behavior and data model together.

The platform-admin allowlist is a separate, verified identity check. Keep the platform-admin account subscription-free and unrestricted without granting platform-wide powers to customer Organization Admins.

### 2. Redis is a production runtime dependency

The backend config defaults Redis to localhost. Celery uses Redis for its broker and result backend, and connector rate limiting also uses Redis. Supabase PostgreSQL does not replace Redis. A production API configured only with a Supabase `DATABASE_URL` would not make these workflows operational.

Before release, choose and test a zero-cost supported approach:
- provision a free Redis-compatible service if one is genuinely available and within its limits; or
- replace the Redis/Celery dependency with a PostgreSQL-backed queue and database-backed rate limiter, with explicit retry, locking, and failure semantics.

Do not silently fall back to localhost or disable rate limiting.

### 3. Import files are stored on a local filesystem

The API saves import files under `IMPORT_STORAGE_DIR`; a separate Celery worker reads those files later. Separate Render services do not automatically share local filesystems. This can cause accepted jobs to fail when the worker cannot see the API's file.

Use private object storage (for example, a private Supabase Storage bucket accessed only by the backend) or another tested shared-storage design. Verify upload, worker read, cleanup, size limits, and access isolation. Do not expose the service-role key to the browser.

### 4. Database security and tenant isolation

The existing two Supabase tables have RLS enabled and no anon/authenticated policies; their intended access is server-only. The new backend tables do not yet have an explicit Supabase security/grant plan.

Before production:
- enable RLS on every new table in the exposed `public` schema;
- explicitly revoke table privileges from `anon` and `authenticated` unless a reviewed frontend use case requires them;
- grant only the backend-required privileges to the server-side database role;
- keep service-role credentials out of frontend bundles;
- verify grants, RLS flags, policies, and Supabase security advisors after migration;
- retain application-level organization scoping and test cross-tenant reads/writes.

The backend currently connects through a PostgreSQL database URL and uses server-side SQLAlchemy queries. RLS alone is not a substitute for its tenant-scoped query checks. Decide whether the runtime connection uses a restricted database role or the Supabase postgres role; do not assume the latter is protected by RLS.

### 5. Migration/model consistency and PostgreSQL version

The backend migration chain and SQLAlchemy metadata need a complete comparison, including constraints, indexes, foreign keys, defaults, and nullability. Existing CI uses PostgreSQL 18 in at least one migration/test workflow, while the target Supabase instance is PostgreSQL 17.11. Run the full migration and regression suite against PostgreSQL 17 before considering it compatible.

The Supabase SQL migration for `contact_requests` and `demo_access` has not been recorded in the live Supabase migration history. Reconcile this carefully; do not reapply a create-table migration against tables that already exist.

### 6. Connection pooling and runtime sizing

The backend SQLAlchemy engine uses a pool (5 connections plus 5 overflow per process). API and worker processes can multiply that demand. Before release:
- use the Supabase Session Pooler for persistent Render services, with TLS required;
- calculate aggregate API + worker connection demand;
- tune SQLAlchemy pool size, overflow, recycle, and timeouts for the project's actual pooler limits;
- test startup, reconnects, concurrent API requests, and worker jobs;
- keep database credentials only in Render secret environment variables.

### 7. Operational behavior

The production entrypoint intentionally does not auto-run Alembic migrations. Preserve that safety. Migrations must be manually applied only after a verified backup and a successful PostgreSQL 17 rehearsal. Production rollback and restore steps must be written and tested.

## Required release gates

- [ ] Role model aligned with one Organization Admin and regular Members; platform-admin bypass remains separate.
- [ ] SQLAlchemy models and Alembic migrations reconciled; one unambiguous Alembic head.
- [ ] Full migrations run successfully on a clean PostgreSQL 17 database.
- [ ] Full backend regression suite passes against PostgreSQL 17.
- [ ] RLS and grants verified for every public table; no unintended anon/authenticated access.
- [ ] Existing `contact_requests` and `demo_access` rows preserved and verified.
- [ ] `demo_access_requests` queue, Supabase mirrors, and notification behavior tested independently.
- [ ] Redis/Celery dependency replaced or provisioned and tested.
- [ ] Import file storage works across API and worker processes.
- [ ] Supabase backup restore test succeeds in a separate database/project.
- [ ] Render connection pool sizing and TLS tested.
- [ ] Staging end-to-end smoke tests pass for signup, login, invitations, subscriptions, imports, demo, contact, reviews, and deletion.
- [ ] Production migration and rollback runbook reviewed.

## Go-live rule

**Do not add `DATABASE_URL` to the Render production service until every blocking gate is closed and the operator receives an explicit instruction to add it.** Adding the variable is not the migration step by itself; it is the final connection cutover after schema deployment and verification.
