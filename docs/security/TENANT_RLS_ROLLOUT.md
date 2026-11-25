# Tenant RLS rollout plan

## Status

Preparation only. This document does not enable tenant policies, change database roles, or switch production credentials. Production remains on its current connection until the application has been made RLS-compatible and verified.

## Required security model

- Keep Supabase Auth JWT verification in the API.
- Resolve the verified JWT subject to the CompatFlow `users` row and its `organization_id`.
- Set a transaction-local organization context only after that mapping succeeds.
- Run tenant queries through a database role with `rolbypassrls = false`; do not use `postgres`, `service_role`, or a table-owner role for normal application traffic.
- Policies must fail closed when the context is absent and apply to both reads and writes (`USING` and `WITH CHECK`).
- Resolve child records through their parent row, not a client-supplied organization identifier.
- Keep platform operations, public demo/contact endpoints, webhook processing, and background workers on separately reviewed, narrowly scoped paths.

## Tenant-owned tables identified in the current model

`compatibility_records`, `connector_rate_limits`, `import_jobs`, `import_record_lineage`, `inventory_snapshots`, `payments`, `product_identifiers`, `product_variants`, `products`, `reviews`, `subscriptions`, `supplier_offers`, `suppliers`, `user_invitations`, `users`, `validation_profiles`, and `validation_rules`.

Child tables without their own organization key include `import_row_errors` (via `import_jobs`) and `review_replies` (via `reviews`). Their policies must check the parent tenant.

## Global or operational tables needing explicit treatment

`organizations`, `subscription_plans`, `role_permissions`, `demo_access`, `demo_access_requests`, `contact_requests`, `payment_webhook_events`, and `alembic_version`.

These must not receive a blanket tenant policy. Access should be granted only to the specific server-side workflows that require them; public access must not be inferred from their global nature.

## Implementation sequence

1. Add transaction-local tenant context support to SQLAlchemy and bind it to the verified user's organization. Ensure it is reset by transaction end and is never accepted from request input.
2. Design a bootstrap path for the initial `users` lookup that does not let an unauthenticated caller choose a tenant. Keep account provisioning and administrative/background workflows separate.
3. Create a restricted application database role and grant only required schema/table/sequence/function privileges. Confirm it does not own tenant tables and has `rolbypassrls = false`.
4. Add explicit RLS policies for each tenant table and parent-checked policies for child tables. Preserve the already-enabled RLS state and existing privilege revocations.
5. Add integration tests for missing context, same-tenant access, cross-tenant SELECT/INSERT/UPDATE/DELETE, child-row access, and connection-pool/transaction reuse.
6. Verify every normal API route, admin path, demo/contact flow, webhook, and worker against the intended role. Deploy to staging and run the workflow suite.
7. Configure the restricted connection in production, deploy, smoke-test, and retain a tested rollback path. Do not switch production while any workflow still depends on RLS bypass.

## Production blocker

The currently shared production connection uses the Supabase `postgres` role, which bypasses RLS. Its password was masked in chat. A restricted role and its connection must be provisioned through the database owner/Supabase controls and configured directly in Render; secrets should not be sent in chat. Applying policies before the backend is RLS-aware can break legitimate requests, while leaving the backend on the bypass role would not enforce the policies.
