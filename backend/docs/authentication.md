# CompatFlow backend authentication and invitations

## Identity provider

Supabase Auth is the identity provider. The backend validates access-token signatures against the project's JWKS endpoint and checks issuer, audience, expiry, subject, and email. Authorization decisions come from the backend PostgreSQL `users` record, not user-editable frontend state or JWT role metadata.

Required backend environment variables:

- `SUPABASE_URL`: project URL, for example `https://<project-ref>.supabase.co`.
- `SUPABASE_ANON_KEY`: the project's public anon key. The invitation acceptance endpoint uses this with the caller's access token to verify `email_confirmed_at`.

Do not put a Supabase service-role key in the backend auth flow or expose it to the browser. Do not commit any keys.

Supabase Auth must use an asymmetric JWT signing key discoverable from `/auth/v1/.well-known/jwks.json` (ES256 or RS256). This backend intentionally rejects HS256 tokens rather than sharing the JWT signing secret with the API.

## Invitation lifecycle

1. A verified, active CompatFlow user with the `owner` or `admin` role calls `POST /api/v1/invitations`.
2. The backend creates a cryptographically random, single-use invitation token. Only its SHA-256 hash is stored in PostgreSQL.
3. The raw token is returned once to the authenticated administrator. The administrator must deliver the invitation link to the intended recipient through an approved channel. Automated email delivery is not wired up yet.
4. The recipient signs in or creates an account through Supabase Auth and verifies the same email address that received the invitation.
5. The recipient calls `POST /api/v1/invitations/accept` with the invitation token and their Supabase access token.
6. The backend verifies the Supabase account's confirmed email, checks the invitation email matches, checks expiry/revocation/reuse, then creates the local organization user and marks the invitation accepted atomically.

Invitation expiry defaults to 72 hours and can be set from 1 to 168 hours. Only `admin`, `member`, and `viewer` can be assigned through invitations. `owner` is reserved for the initial organization bootstrap.

## Endpoints

- `GET /api/v1/auth/me`: current authorized profile.
- `POST /api/v1/invitations`: create an invitation (owner/admin only).
- `GET /api/v1/invitations`: list invitations for the caller's organization (owner/admin only).
- `DELETE /api/v1/invitations/{invitation_id}`: revoke a pending invitation (owner/admin only).
- `POST /api/v1/invitations/accept`: accept a token for the authenticated, verified matching email.

## Initial owner bootstrap

There is intentionally no public endpoint that grants the first owner role. Before issuing invitations, an operator must:

1. Create the initial owner account in Supabase Auth and complete email verification.
2. Create the organization's row in the backend PostgreSQL database.
3. Insert the local `users` row with that Supabase Auth user UUID as `auth_user_id`, the same verified email, the organization UUID, role `owner`, and `is_active = true`.

Run this only through a trusted database administration session. Never expose a bootstrap endpoint or accept organization/role values from an unauthenticated request.

## Deployment order

1. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the backend hosting environment.
2. Deploy the backend code after review.
3. Apply the Alembic migration using the deployment's migration procedure.
4. Bootstrap the initial owner.
5. Test invite, verify-email, accept, expiry, reuse, revoke, and cross-organization access before enabling protected product workflows.

The existing public CSV preview endpoint remains public for now. Persistent catalog import remains disabled. This PR does not yet add tenant-scoped product routes or organization membership across multiple organizations.


## Tenant isolation and catalog permissions

The internal account currently belongs to one organization. The organization context is derived from the authenticated `users` row. Catalog and supplier endpoints never accept an organization ID from the caller.

- `GET /api/v1/products`: requires `catalog:read`; returns only products owned by the caller's organization (maximum 500 per response).
- `GET /api/v1/products/{product_id}`: requires `catalog:read`; foreign-organization IDs return 404.
- `POST /api/v1/products`: requires `catalog:write`; the organization ID is assigned server-side, and an optional supplier must belong to the same organization.
- `GET /api/v1/suppliers`: requires `supplier:read`; returns only suppliers owned by the caller's organization.
- `POST /api/v1/suppliers`: requires `supplier:write`; the organization ID is assigned server-side.

The migration seeds database-backed role permissions:

| Role | Catalog read | Catalog write | Supplier read | Supplier write |
| --- | --- | --- | --- | --- |
| owner | Yes | Yes | Yes | Yes |
| admin | Yes | Yes | Yes | Yes |
| member | Yes | Yes | Yes | Yes |
| viewer | Yes | No | Yes | No |

Database composite foreign keys additionally prevent products from referencing another organization's supplier, compatibility records from referencing another organization's product, and import jobs from referencing another organization's supplier. The migration checks existing data first and aborts with an explicit error if it finds cross-organization relationships.

Public CSV preview remains stateless and public. Persistent catalog import remains disabled. These catalog endpoints are the first protected persistent operations; future catalog routes must use the same server-derived organization scope and permission dependency.
