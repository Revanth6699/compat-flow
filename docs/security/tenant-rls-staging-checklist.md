# Tenant RLS staging verification

This rollout is staging-only. Do not promote the migration to production until the following checks pass against the restricted production runtime role.

## Database checks

- [ ] Alembic revision is `20261125_0014`.
- [ ] Every public application table except `alembic_version` has RLS enabled.
- [ ] Every tenant table has FORCE RLS enabled.
- [ ] The staging runtime role is subject to RLS (it must not have BYPASSRLS).
- [ ] No tenant-owned rows are visible when organization context is absent.

## Tenant isolation

- [ ] Organization A cannot SELECT, UPDATE, or DELETE Organization B's products, suppliers, variants, offers, inventory, compatibility records, imports, errors, lineage, payments, subscriptions, users, invitations, reviews, or connector rate limits.
- [ ] Organization A cannot INSERT or UPDATE a row with Organization B's organization_id.
- [ ] Import row errors are visible only through the owning import job.
- [ ] Review replies follow the parent review's publication and tenant visibility.

## Explicit access paths

- [ ] A verified identity can bootstrap only its own CompatFlow user row.
- [ ] A verified new identity can create one organization and its owner profile.
- [ ] An invitee can read and consume only an invitation issued to their verified email.
- [ ] Public demo requests can insert and read only the request for the submitted email; only the platform admin can review or change decisions.
- [ ] Published reviews and replies remain publicly readable; review writes remain tenant-scoped.
- [ ] Subscription plans and role permissions are readable after authentication.
- [ ] Razorpay webhook writes are permitted only after signature verification.
- [ ] Worker jobs and connector rate-limit sessions are bound to the queue/request tenant.
- [ ] Organization deletion can remove only that organization's rows.

## Release gate

- [ ] CI backend, frontend, industry-ingestion, lint, security, and image-build checks pass.
- [ ] Staging smoke tests pass for onboarding, invitation acceptance, demo request, review display, billing webhook processing, connector preview/commit, import history, and account deletion.
- [ ] Production has a dedicated login role with least-privilege grants and `NOBYPASSRLS`; the application does not connect as `postgres` or `service_role`.
- [ ] Production backup and rollback procedure are verified before migration.
