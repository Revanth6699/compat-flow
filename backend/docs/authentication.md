# Authentication and Organization Access

## Identity and authorization

Supabase Auth provides user identity. The backend validates access tokens against the project's JWKS endpoint and checks the issuer, audience, expiry, subject, and email claims.

Application permissions are read from the user's record in the backend PostgreSQL database. The API does not use frontend state or user-editable JWT role metadata to make authorization decisions.

### Backend configuration

- `SUPABASE_URL`: Supabase project URL, such as `https://<project-ref>.supabase.co`.
- `SUPABASE_ANON_KEY`: Public anon key used by invitation acceptance to verify the confirmed email status.

Do not expose a Supabase service-role key to the browser or use it in the normal authentication flow. Never commit credentials.

The project must use an asymmetric JWT signing key available through `/auth/v1/.well-known/jwks.json` (ES256 or RS256). The backend rejects HS256 tokens rather than sharing a signing secret with the API.

## Invitations

1. An active organization owner or admin creates an invitation through `POST /api/v1/invitations`.
2. The backend generates a random, single-use token and stores only its SHA-256 hash.
3. The raw token is returned once. The administrator must send the invitation link through an approved channel; automated email delivery is not implemented.
4. The recipient creates or signs in to a Supabase Auth account and verifies the invited email address.
5. The recipient accepts the invitation through `POST /api/v1/invitations/accept`.
6. The backend checks the token, expiry, revocation state, single-use state, and verified email match before creating membership.

Invitations expire after 72 hours by default. The configured range is 1–168 hours. Invitations can grant `admin`, `member`, or `viewer` access. The `owner` role is reserved for initial organization setup.

## Authentication endpoints

| Endpoint | Access |
|---|---|
| `GET /api/v1/auth/me` | Current user's authorized profile |
| `POST /api/v1/invitations` | Create an invitation; owner or admin |
| `GET /api/v1/invitations` | List organization invitations; owner or admin |
| `DELETE /api/v1/invitations/{invitation_id}` | Revoke a pending invitation; owner or admin |
| `POST /api/v1/invitations/accept` | Accept an invitation with a verified matching email |

## Organization setup

The first verified user creates an organization through `POST /api/v1/auth/organization`.

The endpoint:

- Requires a valid Supabase access token and confirmed email.
- Creates the organization and owner profile in one database transaction.
- Rejects an identity already linked to a CompatFlow user.
- Uses the unique `users.auth_user_id` constraint to prevent duplicate provisioning.
- Does not accept a role or organization ID from the caller.
- Assigns the creator the `owner` role in the new organization.

There is no unauthenticated endpoint for claiming an existing organization.

Additional users must join through an invitation. In this version, one Supabase identity can belong to one organization and cannot create a second organization.

## Organization data access

The current account model associates each user with one organization. The backend derives the organization from the authenticated user record. Catalog and supplier endpoints must not accept an organization ID supplied by the caller.

| Endpoint | Permission | Scope |
|---|---|---|
| `GET /api/v1/products` | `catalog:read` | Caller organization only; up to 500 records per response |
| `GET /api/v1/products/{product_id}` | `catalog:read` | A record in another organization returns 404 |
| `POST /api/v1/products` | `catalog:write` | Organization is assigned by the server; supplier must belong to that organization |
| `GET /api/v1/suppliers` | `supplier:read` | Caller organization only |
| `POST /api/v1/suppliers` | `supplier:write` | Organization is assigned by the server |

### Role permissions

| Role | Catalog read | Catalog write | Supplier read | Supplier write |
|---|---:|---:|---:|---:|
| owner | Yes | Yes | Yes | Yes |
| admin | Yes | Yes | Yes | Yes |
| member | Yes | Yes | Yes | Yes |
| viewer | Yes | No | Yes | No |

Composite database foreign keys also prevent products, compatibility records, and import jobs from referencing records owned by another organization. The migration checks existing data and stops with an error if it finds cross-organization relationships.

## Deployment and verification

1. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the backend hosting environment.
2. Review and deploy the backend code.
3. Apply the Alembic migration through the approved deployment procedure.
4. Create the initial owner account.
5. Test invitation creation, email verification, acceptance, expiry, reuse, and revocation.
6. Test cross-organization access and role enforcement on every protected route.

The public CSV preview remains stateless and does not require authentication. This document describes the intended backend controls; it is not a production-readiness certification.