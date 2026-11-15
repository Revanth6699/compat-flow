# Backend Operations

## 1. Authentication and organization onboarding

Supabase Auth handles password registration, login, email confirmation, and password recovery. The FastAPI service validates Supabase access tokens and maps authenticated Supabase users to CompatFlow organization profiles.

The first verified user creates an organization through:

`POST /api/v1/auth/organization`

The backend creates the organization and owner profile in one database transaction. The caller cannot choose a role or attach themselves to an existing organization through this endpoint.

The frontend collects full name, organization name, work email, and password. If Supabase requires email confirmation, the callback exchanges the PKCE code for a session and then provisions the organization. If Supabase returns a session immediately, the signup page provisions it directly.

### Required backend environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL URL using the Psycopg 3 driver |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Public anon/publishable key used to verify confirmed email status |
| `REDIS_URL` | Redis connection for Celery and distributed connector rate limiting |
| `CONNECTOR_ALLOWED_HOSTS` | Comma-separated exact hostnames approved for REST API, SFTP, and SQL Server sources |
| `SFTP_KNOWN_HOSTS_PATH` | Path to the managed SSH known-hosts file mounted in the backend runtime |
| `CONNECTOR_RATE_LIMIT_PER_MINUTE` | Per-organization connector preview/commit limit; default 20, allowed range 1–1000 |
| `IMPORT_MAX_UPLOAD_BYTES` | Upload/connector byte limit; default 25 MiB, maximum 50 MiB |
| `MAPPING_AI_BASE_URL` | Optional HTTPS mapping-provider endpoint |
| `MAPPING_AI_API_KEY` | Optional server-side mapping-provider key |
| `MAPPING_AI_MODEL` | Optional mapping-provider model identifier |

Do not configure or expose a Supabase service-role key for onboarding. Never commit credentials.

## 2. Invitations and subsequent users

Additional employees join an existing organization through invitations:

1. An owner or admin creates an invitation through `POST /api/v1/invitations`.
2. The API returns the raw invitation token once. Only its SHA-256 hash is stored in PostgreSQL.
3. The administrator delivers the invitation link through an approved channel. Automated invitation email delivery is not implemented.
4. The recipient creates or signs into a Supabase account using the invited email and confirms that email.
5. The recipient accepts the invitation through `POST /api/v1/invitations/accept`.
6. The backend checks token validity, expiry, revocation, single-use state, verified email, and email match before creating organization membership.

Invitation roles are limited to admin, member, and viewer. Only an owner can invite another administrator. A Supabase identity already linked to an organization cannot join a second organization in this version.

## 3. Multi-source ingestion operations

See [Multi-source ingestion](../docs/multi-source-ingestion.md) for supported formats, connector limits, security boundaries, and incomplete capabilities.

Connector preview and commit routes:
- Require the existing `supplier_catalogs` plan entitlement.
- Require database-backed catalog read/write permission.
- Are scoped to the authenticated organization.
- Are rate-limited through Redis (20 operations per organization per minute by default).
- Fail closed before contacting the source if Redis is unavailable.

Import history stores source type, a sanitized source descriptor, non-secret source metadata, row errors, and record lineage. API tokens, SFTP passwords/private keys, and SQL Server connection URLs are request-scoped and must not be logged or persisted.

### SQL Server runtime

The backend Dockerfile installs Microsoft ODBC Driver 18 and verifies registration through `pyodbc.drivers()` during image build. The runtime connector also checks for the driver.

The deployment operator must confirm that the deployed service actually uses the repository Dockerfile. Installing the Python package does not install the Microsoft ODBC driver.

Provision a dedicated SQL-authenticated login with SELECT permission only on the approved schema, table, or view. Use:
- `Encrypt=yes`
- `TrustServerCertificate=no`
- `ApplicationIntent=ReadOnly`

`ApplicationIntent=ReadOnly` is not a substitute for database permissions. Do not enable SQL Server ingestion until a real connection and permission-boundary test pass.

### Connector credential handling

A reusable connector credential vault is not implemented. Credentials are submitted for one preview/commit request and are not stored as source configuration.

- Do not add secrets to import metadata, mapping templates, or error messages.
- Mount SFTP known-hosts as a managed file.
- Do not accept host keys from the client.

## 4. Staging database migration procedure

Before applying migrations to staging:

1. Create a recoverable backup of the Render staging PostgreSQL database.
2. Verify that the backup can be accessed and restored.
3. Confirm the target database URL is staging, not production.
4. Review the migration status and expected Alembic head.
5. Run the manually triggered **Apply staging database migration** workflow only after the backup is confirmed.
6. The workflow requires the exact input `APPLY` and repository secret `STAGING_DATABASE_URL`.
7. Verify the resulting Alembic revision and run staging smoke tests.

The workflow does not create a database backup. The operator must create and verify the backup separately. Do not run this procedure against production.

## 5. Public demo boundary

The public demo offers stateless CSV product-quality validation and XLS/XLSX product-record preview within the smaller public-demo limit. It does not persist files or catalog records.

Authenticated multi-format file validation/preview covers CSV, XLSX, XLS, JSON, and XML. The current file UI does not expose the backend commit endpoint.

Protected connector commit endpoints persist reviewed rows under the authenticated organization. Keep these capabilities distinct in user-facing copy.

Persistent imports and connector runs remain subscription-gated. Do not change pricing or plan entitlements as part of ingestion work.

## 6. Account and organization deletion

The backend account-deletion endpoint requires the server-only `SUPABASE_SERVICE_ROLE_KEY`. Configure it in the backend secret manager. Never expose it as a `NEXT_PUBLIC_*` variable or commit its value.

### Member or administrator deletion

A member/admin confirms `DELETE MY ACCOUNT`. Their Supabase identity, CompatFlow membership, and personal review are removed. Shared organization records and the organization subscription remain.

### Organization owner deletion

An owner confirms `DELETE ORGANIZATION`. CompatFlow:
1. Requests immediate cancellation of provider subscriptions.
2. Removes linked Supabase identities.
3. Deletes the organization and related memberships, catalog records, import history, reviews, local subscription/payment rows, and related webhook history.

If the payment provider cannot confirm cancellation, deletion stops before local organization data is removed.

Supabase Auth and PostgreSQL cannot participate in one distributed transaction. If Supabase deletes some linked identities and then returns an error, retry deletion; already-absent identities are treated as deleted.

Verify a recoverable backup and understand that this operation is irreversible before enabling it in production.
