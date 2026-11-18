# Supabase PostgreSQL production-readiness audit

**Branch:** `infra/supabase-production-readiness`  
**Audit source:** GitHub `feature/organization-first-onboarding`  
**Status:** Preparation only. PostgreSQL 17 CI and Alembic model-drift checks pass on the latest audit commit. No Supabase schema, data, or Render environment has been changed.

## Decision

Supabase PostgreSQL is a viable candidate for the CompatFlow application database, but production must not be pointed at it until every release gate below is satisfied. The current Render production backend has no `DATABASE_URL`; leave it unset until the explicit go-ahead is given.

## Verified environment facts

- Supabase project `CompatFlow` is active and runs PostgreSQL 17.11 in Seoul.
- A connection test through the Session Pooler succeeded.
- A Supabase public-schema custom-format backup was created on 2026-11-18 and its archive table-of-contents was inspected. This is not yet a proven restore.
- The current public application schema contains `contact_requests` and `demo_access`; both contain existing data and must be preserved.
- The Supabase migration history query returned no recorded migrations. The repository contains a SQL migration for those two tables, so the live schema and migration history need reconciliation rather than blindly reapplying it.
- The backend migration chain on the staging branch currently ends at `20261116_0011_upload_limits`.
- GitHub Actions passed the full backend industry-ingestion regression workflow and full CI (frontend + backend) against PostgreSQL 17 on the corrected audit commit `5b7d874347436780a183dc422283cf74cdf3b273`.
- `alembic check` now passes in both workflows. It previously detected a mismatch between the model's implicit unique constraint and the migration's named unique index on `users.auth_user_id`; the model was corrected to represent the same named unique index. This verifies metadata parity for the current clean CI database, not the live Supabase schema.

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

Current backend code and migrations still support `owner`, `admin`, `member`, and `viewer`. First-user onboarding creates `owner`; invitations accept `admin`, `member`, or `viewer`; only an owner may invite another admin. Billing endpoints also authorize only `owner`. This conflicts with the product decision of one Organization Admin role and invited employees as Members, and with the requirement that customer Organization Admins must not manage subscriptions/billing.

The refactor must cover:
- onboarding role assignment (first customer account becomes `admin`);
- invitation request validation and acceptance (invited users become `member`; remove `viewer` if no read-only role is required);
- member management and authorization dependencies (Organization Admin can manage members/settings, but not billing/subscription or platform settings);
- permission seed rows and role check constraints;
- deletion and organization lifecycle behavior;
- frontend role labels and access controls;
- tests and operational documentation.

Do not simply drop the `owner` role constraint: the existing code relies on it for organization deletion and privilege checks. The settings UI also branches on `owner` to choose between deleting the whole organization and deleting only an individual membership. Billing routes currently require `owner`, while the product requirement says the Organization Admin must not manage billing/subscriptions. Migrate the behavior, data model, UI, and tests together.

A separate lifecycle risk was found in `DELETE /auth/account`: it deletes Supabase Auth identities before committing the relational organization deletion. If deletion of a later member identity fails, earlier identities may already be gone while the CompatFlow database transaction is still uncommitted. The replacement flow needs an explicit, recoverable deletion state/outbox or another idempotent orchestration design; a database transaction cannot roll back completed Supabase Auth API calls. Do not fix this by simply reversing the order: deleting PostgreSQL rows first and then failing to delete Auth identities creates orphaned sign-in identities.

The platform-admin allowlist is a separate, verified identity check. Keep the platform-admin account subscription-free and unrestricted without granting platform-wide powers to customer Organization Admins.

### 2. Redis is a production runtime dependency

The backend config defaults Redis to localhost. Celery uses Redis for its broker and result backend, and connector rate limiting also uses Redis. Supabase PostgreSQL does not replace Redis. A production API configured only with a Supabase `DATABASE_URL` would not make these workflows operational.

Research found that Upstash documents a Celery integration over a TLS Redis URL. Its current free tier is explicitly positioned for prototypes/hobby projects and lists 256 MB data, 10 GB monthly bandwidth, and 500K monthly commands; the free tier does not include the advertised production SLA / multi-zone HA package. Upstash also specifically warns that Celery workers poll Redis while idle, which can consume request quota. This makes it a possible $0 staging/integration-test candidate, not an acceptable production reliability decision without measured workload and an explicit acceptance of the free-tier availability limits.

Before release, choose and test one of these approaches:
- provision a Redis-compatible service with an appropriate production reliability commitment and cost; or
- replace Redis/Celery with a PostgreSQL-backed queue and database-backed rate limiter, preserving explicit retry, locking, idempotency, and failure semantics.

Do not silently fall back to localhost or disable rate limiting. Do not use Upstash's HTTP-only SDK as a drop-in Celery broker; the documented Celery integration uses the TLS Redis protocol.

### 3. Import files are stored on a local filesystem

The API saves import files under `IMPORT_STORAGE_DIR`; a separate Celery worker reads those files later. Separate Render services do not automatically share local filesystems. This can cause accepted jobs to fail when the worker cannot see the API's file.

Use private object storage (for example, a private Supabase Storage bucket accessed only by the backend) or another tested shared-storage design. Verify upload, worker read, cleanup, size limits, and access isolation. Do not expose the service-role key to the browser.

### 4. Cross-system demo approval is not transactionally safe

The platform-admin decision endpoint updates `demo_access_requests`, calls Supabase REST to mirror `contact_requests` and `demo_access`, and only then commits the backend PostgreSQL transaction. If the final commit fails, Supabase can show an approval/revocation that the authoritative backend queue did not commit. The operation needs an outbox/reconciliation design or a clearly defined authoritative commit followed by retryable idempotent synchronization. The UI must show synchronization status rather than implying the two systems are atomically updated.

The demo submission endpoint has the opposite ordering: it commits the backend queue record, then sends Gmail notification (failure is logged). This is safer for persistence, but notification delivery is best-effort and currently has no durable retry record. Treat email as an independently retryable side effect.

### 5. Database security and tenant isolation

The existing two Supabase tables have RLS enabled and no anon/authenticated policies; their intended access is server-only. The new backend tables do not yet have an explicit Supabase security/grant plan.

Before production:
- enable RLS on every new table in the exposed `public` schema;
- explicitly revoke table privileges from `anon` and `authenticated` unless a reviewed frontend use case requires them;
- grant only the backend-required privileges to the server-side database role;
- keep service-role credentials out of frontend bundles;
- verify grants, RLS flags, policies, and Supabase security advisors after migration;
- retain application-level organization scoping and test cross-tenant reads/writes.

The backend currently connects through a PostgreSQL database URL and uses server-side SQLAlchemy queries. RLS alone is not a substitute for its tenant-scoped query checks. Decide whether the runtime connection uses a restricted database role or the Supabase postgres role; do not assume the latter is protected by RLS.

### 6. Migration/model consistency and PostgreSQL version

The backend migration chain and SQLAlchemy metadata need a complete comparison, including constraints, indexes, foreign keys, defaults, and nullability. The current audit branch runs the full migration and regression workflows against PostgreSQL 17 and runs `alembic check` afterward; both workflows passed on commit `5b7d874347436780a183dc422283cf74cdf3b273`. This is a meaningful compatibility gate, but it does not prove compatibility with the live Supabase schema or existing data.

The Supabase SQL migration for `contact_requests` and `demo_access` has not been recorded in the live Supabase migration history. Reconcile this carefully; do not reapply a create-table migration against tables that already exist.

### 7. Connection pooling and runtime sizing

The backend SQLAlchemy engine uses a pool (5 connections plus 5 overflow per process). API and worker processes can multiply that demand. Before release:
- use the Supabase Session Pooler for persistent Render services, with TLS required;
- calculate aggregate API + worker connection demand;
- tune SQLAlchemy pool size, overflow, recycle, and timeouts for the project's actual pooler limits;
- test startup, reconnects, concurrent API requests, and worker jobs;
- keep database credentials only in Render secret environment variables.

### 8. Operational behavior

The production entrypoint intentionally does not auto-run Alembic migrations. Preserve that safety. Migrations must be manually applied only after a verified backup and a successful PostgreSQL 17 rehearsal. Production rollback and restore steps must be written and tested.

## Required release gates

- [ ] Role model aligned with one Organization Admin and regular Members; platform-admin bypass remains separate.
- [ ] Organization/account deletion redesigned as a recoverable, idempotent workflow across Supabase Auth and PostgreSQL.
- [ ] Demo approval/revocation synchronization made retryable and reconciled across the backend queue and Supabase mirrors.
- [ ] Gmail notification failures have durable retry/reconciliation behavior, or are explicitly surfaced as best-effort.
- [ ] SQLAlchemy models and Alembic migrations reconciled; one unambiguous Alembic head.
- [ ] Full migrations run successfully on a clean PostgreSQL 17 database.
- [ ] Full backend regression suite passes against PostgreSQL 17.
- [ ] RLS and grants verified for every public table; no unintended anon/authenticated access.
- [ ] Existing `contact_requests` and `demo_access` rows preserved and verified.
- [ ] `demo_access_requests` queue, Supabase mirrors, and notification behavior tested independently.
- [ ] Redis/Celery dependency replaced or provisioned with an accepted reliability/cost profile and tested. Upstash Free is not accepted as production-ready solely because it is $0.
- [ ] Import file storage works across API and worker processes.
- [ ] Supabase backup restore test succeeds in a separate database/project.
- [ ] Render connection pool sizing and TLS tested.
- [ ] Staging end-to-end smoke tests pass for signup, login, invitations, subscriptions, imports, demo, contact, reviews, and deletion.
- [ ] Production migration and rollback runbook reviewed.

## Go-live rule

**Do not add `DATABASE_URL` to the Render production service until every blocking gate is closed and the operator receives an explicit instruction to add it.** Adding the variable is not the migration step by itself; it is the final connection cutover after schema deployment and verification.
