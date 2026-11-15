# Backend Operations

This guide covers account setup, invitations, supplier ingestion, staging migrations, and account deletion. It describes repository behavior; verify the target environment before running an operational procedure.

## Authentication and organization setup

Supabase Auth handles registration, login, email confirmation, and password recovery. The FastAPI service validates Supabase access tokens and links authenticated users to CompatFlow organization profiles.

The first verified user creates an organization through:

`POST /api/v1/auth/organization`

The backend creates the organization and owner profile in one database transaction. The caller cannot select a role or attach the account to an existing organization through this endpoint.

The signup form collects the user's name, organization name, work email, and password. When email confirmation is enabled, the callback exchanges the PKCE code for a session before creating the organization. When Supabase returns a session immediately, the signup page creates it directly.

### Backend environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL using the Psycopg 3 driver |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Public anon/publishable key used to check confirmed email status |
| `REDIS_URL` | Redis connection for Celery and distributed connector rate limits |
| `CONNECTOR_ALLOWED_HOSTS` | Exact hostnames approved for REST, SFTP, and SQL Server sources |
| `SFTP_KNOWN_HOSTS_PATH` | Path to the managed SSH known-hosts file mounted in the backend |
| `CONNECTOR_RATE_LIMIT_PER_MINUTE` | Per-organization connector preview/commit limit; default 20, range 1–1,000 |
| `IMPORT_MAX_UPLOAD_BYTES` | Upload and connector byte limit; default 25 MiB, maximum 50 MiB |
| `MAPPING_AI_BASE_URL` | Optional HTTPS mapping-provider endpoint |
| `MAPPING_AI_API_KEY` | Optional server-side mapping-provider key |
| `MAPPING_AI_MODEL` | Optional provider model identifier |

Do not expose a Supabase service-role key during onboarding. Never commit credentials.

## Invitations

Additional employees join an organization through an invitation:

1. An owner or admin creates an invitation through `POST /api/v1/invitations`.
2. The API returns the raw invitation token once. PostgreSQL stores only its SHA-256 hash.
3. The administrator sends the invitation link through an approved channel. Automated email delivery is not implemented.
4. The recipient creates or signs in to a Supabase account using the invited email address and confirms that address.
5. The recipient accepts the invitation through `POST /api/v1/invitations/accept`.
6. The backend checks validity, expiry, revocation, single-use state, and verified email match before creating membership.

Invitation roles are `admin`, `member`, and `viewer`. Only an owner can invite another administrator. In this version, a Supabase identity already linked to an organization cannot join a second one.

## Supplier ingestion

See [Multi-source ingestion](../docs/multi-source-ingestion.md) for the supported formats, connector limits, and current verification status.

Connector preview and commit routes:
- Require the `supplier_catalogs` plan entitlement.
- Require database-backed catalog read/write permission.
- Use the authenticated user's organization as the tenant scope.
- Are limited through Redis to 20 operations per organization per minute by default.
- Stop before contacting the source if Redis is unavailable.

Import history records the source type, a sanitized source descriptor, non-secret metadata, row errors, and record lineage. API tokens, SFTP passwords/private keys, and SQL Server connection URLs are request-scoped. Do not log or persist them.

### SQL Server runtime

The backend Dockerfile installs Microsoft ODBC Driver 18 and checks its registration through `pyodbc.drivers()` during the image build. The connector checks for the driver again at runtime.

Confirm that the deployed service uses the repository Dockerfile. Installing the Python package alone does not install the Microsoft ODBC driver.

Use a dedicated SQL-authenticated login with SELECT permission only on the approved schema, table, or view. Configure:

- `Encrypt=yes`
- `TrustServerCertificate=no`
- `ApplicationIntent=ReadOnly`

`ApplicationIntent=ReadOnly` is not an access-control boundary. Do not enable SQL Server ingestion until a real connection and permission test have passed.

### Connector credentials

A reusable connector credential vault is not implemented. Credentials are supplied for one preview or commit request and are not saved as source configuration.

- Keep secrets out of import metadata, mapping templates, and error messages.
- Mount SFTP known-hosts as a managed file.
- Do not accept SSH host keys from the client.

## Staging database migrations

Before applying a migration to staging:

1. Create a backup of the Render staging PostgreSQL database.
2. Confirm that the backup is accessible and can be restored.
3. Check that the target connection points to staging, not production.
4. Review the migration status and expected Alembic head.
5. Run the manually triggered **Apply staging database migration** workflow only after the backup is verified.
6. Supply the exact workflow input `APPLY` and the repository secret `STAGING_DATABASE_URL`.
7. Verify the resulting Alembic revision and run staging smoke tests.

The workflow does not create a backup. The operator is responsible for creating and verifying it. Never use this procedure against production.

## Public demo and authenticated workflows

The public demo provides stateless CSV product-quality validation and XLS/XLSX product-record preview within the public-demo limits. It does not save files or catalog records.

Authenticated file preview supports CSV, XLSX, XLS, JSON, and XML. The current file interface does not expose the backend file-commit endpoint.

Protected connector commit endpoints can save reviewed rows under the authenticated organization. Keep this separate from the public demo when describing the product.

Persistent imports and connector runs remain subscription-gated. Do not change plan entitlements or pricing as part of ingestion work.

## Account and organization deletion

The account-deletion endpoint requires the server-only `SUPABASE_SERVICE_ROLE_KEY`. Store it in the backend secret manager. Never expose it through a `NEXT_PUBLIC_*` variable or commit its value.

### Member or administrator

The user confirms `DELETE MY ACCOUNT`. The backend removes their Supabase identity, CompatFlow membership, and personal review. Shared organization records and the organization subscription remain.

### Organization owner

The owner confirms `DELETE ORGANIZATION`. CompatFlow:

1. Requests immediate cancellation of provider subscriptions.
2. Removes linked Supabase identities.
3. Deletes the organization and related memberships, catalog records, import history, reviews, local subscription/payment rows, and webhook history.

If the payment provider does not confirm cancellation, deletion stops before local organization data is removed.

Supabase Auth and PostgreSQL do not share a distributed transaction. If some Supabase identities are deleted before an error occurs, retry the operation; identities that are already absent are treated as deleted.

Verify a recoverable backup and confirm the consequences before enabling this operation in production. Organization deletion is irreversible.