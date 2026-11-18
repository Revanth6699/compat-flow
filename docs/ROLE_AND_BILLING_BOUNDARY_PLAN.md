# Organization Roles and Billing Boundary Implementation Plan

## Scope

Implement the confirmed CompatFlow authority model on a branch separate from the production-readiness audit. This plan is not authorization to change production data or environment variables.

## Target authority model

| Principal | Allowed | Explicitly denied |
|---|---|---|
| Platform Admin | Platform-wide organization administration, demo approvals, subscription assignment and billing operations, platform settings, unrestricted testing | No customer subscription required |
| Organization Admin | Manage its own organization profile, members, invitations, and entitled catalog workflows | Platform settings, platform-wide customer administration, subscription creation/cancellation or billing mutation |
| Member | Use organization workflows granted by the plan and product permissions | Organization administration, invitations, role changes, billing, platform administration |
| Viewer (legacy compatibility) | Existing read-only access only, until an explicit migration/review | No write or administration privileges |
| Demo account | Approved demo workflows within 10,000 records and 5 MB | Organization administration, billing, platform administration |

## Verified implementation conflicts

1. New organization onboarding currently writes `role="owner"`.
2. Invitation creation accepts `admin`, `member`, and `viewer`; the current code allows an owner to invite another admin.
3. Member updates accept `admin`, `member`, and `viewer`; owner-only promotion rules are embedded in the endpoint.
4. Member management and invitation endpoints treat both owner and admin as administrators, but also preserve a special owner hierarchy.
5. Account deletion treats owner as the organization-wide deletion principal.
6. The billing API currently authorizes create, checkout verification, and cancellation through `require_roles("owner")`, and uses the caller's own organization. This does not match platform-admin-controlled subscription operations.
7. The billing page currently offers checkout and cancellation to the owner role and tells other users to contact the owner.
8. The role-permission table has a database check constraint that explicitly includes owner, admin, member, and viewer.

## Required implementation sequence

### 1. Define compatibility-safe role semantics

- Use `admin` as the one canonical customer Organization Admin role for new accounts.
- Keep `owner` as a temporary legacy alias during migration and rollout; it must not create a second customer-admin tier.
- New invitations must create Members only. Do not expose an Organization Admin promotion path to customer admins.
- Preserve `viewer` as read-only. Do not silently convert viewers into members.
- Keep Platform Admin identity in the separate configured email allowlist; never infer platform authority from a customer role.
- Update backend authorization, UI labels, and tests together.

### 2. Separate platform subscription administration

- Customer Organization Admins may read their organization's current plan and entitlements.
- Customer-facing UI must not expose subscription create, cancel, or billing mutation actions.
- Add platform-admin-only operations that explicitly identify the target organization and validate the target plan/status.
- Keep payment-provider webhooks authenticated independently; do not gate webhooks behind an interactive user role.
- Preserve the platform-admin subscription exemption.
- Do not simply change the existing owner-only endpoints to platform-admin-only while they still derive the target organization from the caller's profile. That would target the platform admin's own organization, not the selected customer organization.

### 3. Make organization deletion semantics explicit

- Organization Admin manages its organization, but account deletion and whole-organization deletion are separate destructive actions.
- Preserve safe confirmation and provider cancellation checks.
- Replace cross-system delete ordering with a recoverable deletion workflow before claiming reliable account deletion.
- Do not delete Supabase identities one by one inside an ordinary SQL transaction and assume the external calls can roll back.

### 4. Database migration and compatibility

- Inventory actual role values and all role-dependent permission rows before migration.
- Migrate legacy `owner` customer profiles to `admin` only after the application supports both values.
- Keep `viewer` unchanged and preserve its read-only permissions.
- Update role-permission constraints and seed data in a forward-only migration.
- Test the migration against a PostgreSQL 17 staging clone and verify downgrade/rollback strategy before any production application.
- Never run this migration against production as part of deployment startup.

### 5. Validation gates

- Tests for signup role, invitation defaults, forbidden admin promotion, viewer read-only behavior, and organization isolation.
- Tests proving customer admins cannot mutate subscriptions or billing.
- Tests proving platform admin can administer a specified customer organization without being bound to its own organization.
- Frontend checks: no checkout/cancel controls for customer users; customer plan/entitlement visibility remains.
- Full CI, Alembic parity, and staging end-to-end checks must pass before merging.
- No Render `DATABASE_URL` change until all production-readiness gates, including a restore rehearsal, are closed.

## Safety status

- This is an implementation plan only.
- No database migration has been applied.
- No production environment variable has been changed.
- No production data has been modified.
