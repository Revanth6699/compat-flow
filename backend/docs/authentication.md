# Authentication and Tenant Access

## 1. Identity provider

Supabase Auth is the identity provider. The backend validates access-token signatures against the project's JWKS endpoint and checks issuer, audience, expiry, subject, and email.

Authorization decisions come from the backend PostgreSQL `users` record, not user-editable frontend state or JWT role metadata.

### Required backend environment

- `SUPABASE_URL`: Supabase project URL, for example `https://<project-ref>.supabase.co`.
- `SUPABASE_ANON_KEY`: public anon key. The invitation acceptance endpoint uses this with the caller's access token to verify `email_confirmed_at`.

Do not put a Supabase service-role key in the backend authentication flow or expose it to the browser. Do not commit keys.

Supabase Auth must use an asymmetric JWT signing key discoverable from `/auth/v1/.well-known/jwks.json` (ES256 or RS256). This backend intentionally rejects HS256 tokens rather than sharing the JWT signing secret with the API.

## 2. Invitation lifecycle

1. A verified, active CompatFlow owner or admin calls `POST /api/v1/invitations`.
2. The backend creates a cryptographically random, single-use invitation token. Only its SHA-256 hash is stored in PostgreSQL.
3. The raw token is returned once. The administrator must deliver the invitation link through an approved channel. Automated email delivery is not implemented.
4. The recipient signs in or creates a Supabase Auth account and verifies the invited email address.
5. The recipient calls `POST /api/v1/invitations/accept` with the token and Supabase access token.
6. The backend verifies the confirmed email, email match, expiry, revocation, and single-use state, then creates the organization user and marks the invitation accepted atomically.

Invitation expiry defaults to 72 hours and can be configured from 1 to 168 hours. Invitations can assign `admin`, `member`, or `viewer`. The `owner` role is reserved for initial organization bootstrap.

## 3. Endpoints

| Endpoint | Access |
|---|---|
| `GET /api/v1/auth/me` | Current authorized profile |
| `POST /api/v1/invitations` | Create invitation; owner/admin |
| `GET /api/v1/invitations` | List organization invitations; owner/admin |
| `DELETE /api/v1/invitations/{invitation_id}` | Revoke pending invitation; owner/admin |
| `POST /api/v1/invitations/accept` | Accept token for authenticated, verified matching email |

## 4. Organization onboarding

The first verified user creates an organization through `POST /api/v1/auth/organization`.

The endpoint:
- Requires a valid Supabase access token and confirmed email.
- Creates the organization and owner profile in one database transaction.
- Rejects an identity already linked to a CompatFlow user.
- Relies on the unique `users.auth_user_id` constraint to prevent concurrent duplicate provisioning.
- Does not accept a role or organization ID from the caller.
- Assigns the creator the `owner` role for the newly created organization.

There is no public first-owner bootstrap endpoint that allows an unauthenticated visitor to claim an existing organization.

Subsequent users must join through an invitation. A Supabase identity cannot create a second organization in this version. The current data model supports one organization per Supabase user.

## 5. Tenant isolation and catalog permissions

The current account model links each user to one organization. Organization context is derived from the authenticated `users` row. Catalog and supplier endpoints must not accept an organization ID from the caller.

| Endpoint | Permission | Tenant rule |
|---|---|---|
| `GET /api/v1/products` | `catalog:read` | Returns only caller-organization products; maximum 500 per response |
| `GET /api/v1/products/{product_id}` | `catalog:read` | Foreign-organization IDs return 404 |
| `POST /api/v1/products` | `catalog:write` | Organization assigned server-side; supplier must belong to same organization |
| `GET /api/v1/suppliers` | `supplier:read` | Returns only caller-organization suppliers |
| `POST /api/v1/suppliers` | `supplier:write` | Organization assigned server-side |

### Seeded role permissions

| Role | Catalog read | Catalog write | Supplier read | Supplier write |
|---|---:|---:|---:|---:|
| owner | Yes | Yes | Yes | Yes |
| admin | Yes | Yes | Yes | Yes |
| member | Yes | Yes | Yes | Yes |
| viewer | Yes | No | Yes | No |

Database composite foreign keys also prevent products from referencing another organization's supplier, compatibility records from referencing another organization's product, and import jobs from referencing another organization's supplier.

The migration checks existing data and aborts with an explicit error if cross-organization relationships are found.

## 6. Deployment and verification order

1. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the backend hosting environment.
2. Review and deploy backend code.
3. Apply the Alembic migration through the approved deployment procedure.
4. Bootstrap the initial owner.
5. Test invitation creation, email verification, acceptance, expiry, reuse, revocation, and cross-organization access.
6. Test every protected route for server-derived tenant scope and role enforcement before enabling customer workflows.

The public CSV preview endpoint remains stateless and public. Persistent catalog import and additional tenant-scoped product workflows must be treated according to their current implementation and release gates. This document does not certify production readiness.
