# Backend operations

## Self-service organization onboarding

Supabase Auth owns password registration, login, email confirmation, and password recovery. The FastAPI service validates Supabase access tokens and maps authenticated Supabase users to CompatFlow organization profiles.

The first user creates an organization through the authenticated `POST /api/v1/auth/organization` endpoint after confirming their email. The backend creates the organization and owner profile in one transaction. The caller cannot choose a role or attach themselves to an existing organization through this endpoint.

The frontend signup form collects full name, organization name, work email, and password. If Supabase requires email confirmation, the callback exchanges the PKCE code for a session and then provisions the organization. If Supabase returns a session immediately, the signup page provisions it directly.

### Required backend environment

- `DATABASE_URL`: PostgreSQL URL using the Psycopg 3 driver.
- `SUPABASE_URL`: Supabase project URL.
- `SUPABASE_ANON_KEY`: Supabase public anon/publishable key used to verify confirmed email status.

Do not configure or expose a Supabase service-role key for this flow. Never commit credentials.

## Subsequent users and invitations

Additional employees join an existing organization through invitations:

1. An owner or admin creates an invitation through `POST /api/v1/invitations`.
2. The API returns the raw invitation token once. Only its SHA-256 hash is stored in PostgreSQL.
3. The administrator must deliver the invitation link through an approved channel. Automated invitation email delivery is not implemented.
4. The recipient creates or signs into a Supabase account using the invited email and confirms that email.
5. The recipient accepts the invitation through `POST /api/v1/invitations/accept`.
6. The backend checks the token, expiry, revocation, single-use state, verified email, and email match before creating the organization membership.

Invitation roles are limited to `admin`, `member`, and `viewer`. Only an owner can invite another administrator. A Supabase identity already linked to an organization cannot join a second organization in this version.

## Staging migration procedure

Before applying migrations to staging:

1. Create and verify a recoverable backup of the Render staging PostgreSQL database.
2. Confirm the target database URL is the staging database, not production.
3. Review the migration status and expected Alembic head.
4. Run the manually triggered **Apply staging database migration** GitHub Actions workflow only after the backup is confirmed. The workflow requires the exact input `APPLY` and the repository secret `STAGING_DATABASE_URL`.
5. Verify the resulting Alembic revision and run the staging smoke tests.

The workflow does not create a database backup. The operator must create and verify the backup separately before authorizing it. Do not run the workflow against production.

## Public demo boundary

The public CSV preview remains available without authentication. It validates uploads in memory and does not persist files or catalog records. Persistent imports remain disabled. Protected supplier and catalog endpoints derive organization scope from the authenticated backend profile and enforce database-backed role permissions.
