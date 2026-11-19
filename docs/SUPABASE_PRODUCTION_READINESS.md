# Supabase PostgreSQL production-readiness audit

**Branch:** `infra/supabase-production-readiness`  
**Audit source:** GitHub `feature/organization-first-onboarding`  
**Status:** Preparation only. PostgreSQL 17 CI and Alembic model-drift checks pass on the latest audit commit. Production Supabase schema/data have not been changed and no production migrations have been run. The production Render service environment was updated on 2026-11-19 and the resulting deploy succeeded; this audit does not alter or expose its secret values.

## Decision

Supabase PostgreSQL is the configured database target for the Render production backend, but the production application schema is not yet ready for the current application release. Do not unset, replace, or repoint the existing production `DATABASE_URL`. Do not run migrations or deploy the feature branch until every release gate below is satisfied and a restorable backup is verified. The Render service API confirms a successful environment-triggered deploy, but does not reveal secret values or prove application-level database queries.

## Verified environment facts

- Supabase project `CompatFlow` is active and runs PostgreSQL 17.11 in Seoul.
- A connection test through the Session Pooler succeeded.
- A Supabase public-schema custom-format backup was created on 2026-11-18 and its archive table-of-contents was inspected. This is not yet a proven restore.
- The current public application schema contains `contact_requests` and `demo_access`; both contain existing data and must be preserved.
- The Supabase migration history query returned no recorded migrations. The repository contains a SQL migration for those two tables, so the live schema and migration history need reconciliation rather than blindly reapplying it.
- The backend migration chain on the staging branch currently ends at `20261116_0011_upload_limits`.
- The staging rows (2 organizations, 2 users, 7 demo requests) are test records, not original customer/business records. They are not production seed data and must not be copied into production. They should still not be deleted without explicit approval.
- GitHub Actions full CI passed (backend + frontend) against PostgreSQL 17 on audit commit `94b897133ef68e6af07177eeef67f41c1f6b6575`.
- `alembic check` now passes in both workflows. It previously detected a mismatch between the model's implicit unique constraint and the migration's named unique index on `users.auth_user_id`; the model was corrected to represent the same named unique index. This verifies metadata parity for the current clean CI database, not the live Supabase schema.

## Production snapshot verified on 2026-11-19

- Render production web service `compat-flow` is on the Free plan, deploys from `main`, and its latest environment-triggered deploy completed successfully. This is not evidence that database-backed routes work.
- The production health route is implemented as a static `status=ok` response and does not execute a database query. It is a liveness check only, not a readiness or database-connectivity check.
- Production Supabase currently has exactly two public application tables:
  - `contact_requests`: 6 rows.
  - `demo_access`: 2 rows.
- Production `public.alembic_version` does not exist; the live Supabase migration history is empty.
- Staging PostgreSQL has 21 public tables including `alembic_version`, and is at migration head `20261116_0011`. The selected staging data counts are: 2 organizations, 2 users, 7 `demo_access_requests`, and 0 subscriptions, payments, products, suppliers, import jobs, or reviews.
- The production and staging databases are not interchangeable. Do not copy staging data into production. Build and rehearse a migration against a separate empty PostgreSQL 17 database, then prepare a preservation-aware migration for the two existing production tables.
- The production Render service has no persistent disk configured in its service definition. Any workflow that depends on local import-file persistence must be redesigned or backed by private shared object storage before production use.

## Verified free-tier runtime topology (2026-11-19)

The Render account's current CompatFlow resources contain two web services only:

- Production API: `compat-flow`, Free plan, branch `main`, health check `/api/v1/health`.
- Staging API: `compat-flow-staging`, Free plan, branch `feature/organization-first-onboarding`.
- No dedicated CompatFlow Celery worker or Redis/Key Value resource appears in the current Render service inventory. This is a verified account inventory snapshot, not proof that no external Redis service exists elsewhere.
- The current application configuration defaults Redis, Celery broker, and Celery result backend to localhost. No production Redis endpoint has been verified.
- The backend defines a Celery worker task for catalog import processing. A worker process must be deployed and connected to the same broker before those asynchronous tasks can execute.
- Connector preview/commit rate limiting calls Redis and deliberately returns HTTP 503 when Redis is unavailable; it does not fail open.
- Import files are written under `IMPORT_STORAGE_DIR` (default `/data/imports`) on the API filesystem. The worker reads that same path. The production Render service has no persistent disk, and separate services do not share local filesystems.

**Immediate impact:** database-backed API routes may work with the configured Supabase URL, but connector workflows that require Redis currently have no verified production Redis dependency, and asynchronous file-import processing has no verified worker/shared-file setup. Do not advertise those workflows as operational until the full path is tested.

Free-tier implementation decision must be explicit:
- Prefer a PostgreSQL-backed durable job queue and rate limiter if the goal is strictly $0 and operational simplicity; implement row locking/leases, bounded retries, idempotency, stale-job recovery, and rate-limit atomicity.
- If retaining Celery, use a compatible Redis service and a separate worker only after confirming a sustainable free tier and accepting its availability/quota limits.
- Move import files to private shared object storage or redesign processing so files are streamed/processed within one request with safe limits; never rely on Render ephemeral disk for jobs that outlive the request.

## Confirmed product authority and access model

The platform is operated by the platform administrator account configured as `sarvasettyrevanth.66@gmail.com`. This is a platform-level identity, not an organization role, and it remains separate from customer organization membership.

The intended access boundaries are:

| Account type | Authority |
|---|---|
| Platform Administrator | Operates the website and platform; manages customer organizations, demo approvals, subscription plans/assignments, billing operations, and platform-wide settings. The platform-admin account is subscription-exempt. |
| Customer Organization Admin | Controls their own organization: organization profile/settings, member invitations and access, and organization workspaces/catalog operations allowed by its subscription. Cannot access platform administration or independently change subscription/billing. |
| Organization Member | Uses the organization's permitted product workflows and data; cannot administer the organization, manage members, billing, or platform settings. |
| Demo account/requester | Has limited demo access only; no customer organization administration or subscription/billing controls. Demo entitlements must enforce the demo limits (10,000 records and 5 MB) server-side. |

Subscription plans remain the source of customer feature entitlements and upload limits. The platform administrator owns subscription administration and billing operations; customer Organization Admins can see their current plan/entitlements and use the features granted by it, but cannot change the plan or billing state. Do not remove the public pricing/plan comparison experience or weaken plan-based entitlements while enforcing this boundary.

Invited users must be regular Members by default. Do not expose an Owner role or allow a customer to promote an invited Member into Organization Admin through the existing legacy role flow. Existing legacy `owner` and `admin` records must be safely mapped to the single Organization Admin concept during a reviewed migration; existing `member` and `viewer` records require an explicit compatibility decision so read-only access is not accidentally widened.

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

Current backend code and migrations still support `owner`, `admin`, `member`, and `viewer`. First-user onboarding creates `owner`; invitations accept `admin`, `member`, or `viewer`; only an owner may invite another admin. Billing endpoints also authorize only `owner`. This conflicts with the confirmed authority model above: one customer Organization Admin role, invited employees as Members, and platform-admin-only subscription/billing administration.

The refactor must cover:
- onboarding role assignment (first customer account becomes the single Organization Admin role, with no Owner/Administrator split);
- invitation request validation and acceptance (invited users become `member` by default; preserve or explicitly migrate existing read-only `viewer` behavior rather than silently granting extra permissions);
- member management and authorization dependencies (Organization Admin can manage their own organization/members/settings, but not billing/subscription or platform settings);
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

The current Celery task has late acknowledgements and a prefetch multiplier of one, but no explicit retry/backoff or dead-letter policy. It marks a job failed when processing raises. Before enabling retries, make processing idempotent across attempts and define how duplicate row errors, partial commits, worker crashes, and stale `processing` jobs are reconciled. A retry must not silently double-count or leave an import permanently stuck.

### 4. Cross-system demo approval is not transactionally safe

The platform-admin decision endpoint updates `demo_access_requests`, calls Supabase REST to mirror `contact_requests` and `demo_access`, and only then commits the backend PostgreSQL transaction. If the final commit fails, Supabase can show an approval/revocation that the authoritative backend queue did not commit. The operation needs an outbox/reconciliation design or a clearly defined authoritative commit followed by retryable idempotent synchronization. The UI must show synchronization status rather than implying the two systems are atomically updated.

The demo submission endpoint has the opposite ordering: it commits the backend queue record, then sends Gmail notification (failure is logged). This is safer for persistence, but notification delivery is best-effort and currently has no durable retry record. Treat email as an independently retryable side effect. The general contact endpoint currently writes the contact row first and then calls Gmail; the notification endpoint reports `email_sent: false` on delivery failure, but there is no durable notification record or retry worker. The demo backend endpoint similarly saves the queue row and attempts Gmail afterward. Add a persisted notification outbox with bounded retries, backoff, delivery timestamps, and visible failure state; do not make a successful contact/demo submission depend on Gmail being available.

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

**The production Render service already has its database connection configured. Do not unset, replace, or repoint it. Do not run production migrations or deploy the staging feature branch until every blocking gate is closed, the backup restore is verified, and the migration has passed rehearsal.** The configured connection alone is not evidence that the live application schema is ready.
