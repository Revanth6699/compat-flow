# Backend operations

## Authentication and organization onboarding

Supabase Auth owns password registration, login, email confirmation, and password recovery. The FastAPI service validates Supabase access tokens and maps authenticated Supabase users to CompatFlow organization profiles.

The first user creates an organization through the authenticated POST /api/v1/auth/organization endpoint after confirming their email. The backend creates the organization and owner profile in one transaction. The caller cannot choose a role or attach themselves to an existing organization through this endpoint.

The frontend signup form collects full name, organization name, work email, and password. If Supabase requires email confirmation, the callback exchanges the PKCE code for a session and then provisions the organization. If Supabase returns a session immediately, the signup page provisions it directly.

### Required backend environment

- DATABASE_URL: PostgreSQL URL using the Psycopg 3 driver.
- SUPABASE_URL: Supabase project URL.
- SUPABASE_ANON_KEY: Supabase public anon/publishable key used to verify confirmed email status.
- REDIS_URL: Redis connection used for Celery and distributed connector rate limiting.
- CONNECTOR_ALLOWED_HOSTS: comma-separated exact hostnames approved for REST API, SFTP, and SQL Server sources.
- SFTP_KNOWN_HOSTS_PATH: path to the managed SSH known-hosts file mounted in the backend runtime.
- CONNECTOR_RATE_LIMIT_PER_MINUTE: per-organization connector preview/commit limit; defaults to 20 and must be 1–1000.
- IMPORT_MAX_UPLOAD_BYTES: upload/connector byte limit; defaults to 25 MiB and cannot exceed 50 MiB.
- MAPPING_AI_BASE_URL, MAPPING_AI_API_KEY, MAPPING_AI_MODEL: optional server-side mapping provider configuration. Do not set these unless the provider, retention terms, and cost are approved.

Do not configure or expose a Supabase service-role key for onboarding. Never commit credentials.

## Subsequent users and invitations

Additional employees join an existing organization through invitations:

1. An owner or admin creates an invitation through POST /api/v1/invitations.
2. The API returns the raw invitation token once. Only its SHA-256 hash is stored in PostgreSQL.
3. The administrator must deliver the invitation link through an approved channel. Automated invitation email delivery is not implemented.
4. The recipient creates or signs into a Supabase account using the invited email and confirms that email.
5. The recipient accepts the invitation through POST /api/v1/invitations/accept.
6. The backend checks the token, expiry, revocation, single-use state, verified email, and email match before creating the organization membership.

Invitation roles are limited to admin, member, and viewer. Only an owner can invite another administrator. A Supabase identity already linked to an organization cannot join a second organization in this version.

## Multi-source ingestion operations

See the multi-source ingestion guide for the format matrix, API pagination and retry limits, SQL Server watermark requirements, security boundaries, and incomplete capabilities.

Connector preview and commit routes require the existing supplier_catalogs plan entitlement and a database-backed catalog:read or catalog:write permission. Redis enforces a fixed-window per-organization request limit; if Redis is unavailable, connector execution fails closed. Import history stores source type, a sanitized source descriptor, non-secret source metadata, row errors, and record lineage. API tokens, SFTP passwords/private keys, and SQL Server connection URLs are request-scoped and must not be written to logs or persisted.

### SQL Server runtime requirement

The backend Dockerfile installs Microsoft ODBC Driver 18 for SQL Server and verifies its registration through pyodbc.drivers() during image build. The runtime connector also checks that the driver exists before connecting. The deployment operator must confirm that the deployed service actually uses the repository Dockerfile. Python package installation alone does not install the Microsoft ODBC driver.

Provision a dedicated SQL-authenticated login with only SELECT on the approved schema/table/view. Use Encrypt=yes, TrustServerCertificate=no, and ApplicationIntent=ReadOnly; the latter is not a substitute for database permissions. Do not enable SQL Server ingestion until a real test connection and permission-boundary test pass.

### Connector credential handling

There is no reusable connector credential vault yet. Credentials are submitted for one preview/commit request and are not stored as source configuration. Do not add secrets to import metadata, mapping templates, or error messages. SFTP known-hosts must be mounted as a managed file; do not accept host keys from the client.

## Staging migration procedure

Before applying migrations to staging:

1. Create and verify a recoverable backup of the Render staging PostgreSQL database.
2. Confirm the target database URL is the staging database, not production.
3. Review the migration status and expected Alembic head.
4. Run the manually triggered Apply staging database migration workflow only after the backup is confirmed. The workflow requires the exact input APPLY and the repository secret STAGING_DATABASE_URL.
5. Verify the resulting Alembic revision and run the staging smoke tests.

The workflow does not create a database backup. The operator must create and verify the backup separately before authorizing it. Do not run the workflow against production.

## Public demo boundary

The public demo offers stateless CSV product-quality validation and XLS/XLSX product-record preview within the smaller public demo limit. It does not persist files or catalog records. Authenticated multi-format file validation/preview covers CSV, XLSX, XLS, JSON, and XML, but the current file UI does not expose the backend commit endpoint. Protected connector commit endpoints persist reviewed rows under the authenticated organization. Keep these capabilities clearly separated in UI copy.

Persistent imports and connector runs remain subscription-gated. Do not change pricing or plan entitlements as part of ingestion work.


## Account and organization deletion

The backend account deletion endpoint requires a server-only `SUPABASE_SERVICE_ROLE_KEY`. Configure it in the backend secret manager; never expose it as a `NEXT_PUBLIC_*` variable or commit its value.

- A member/admin confirms `DELETE MY ACCOUNT`: their Supabase identity, CompatFlow membership and personal review are removed. Shared organization records and the organization subscription remain.
- An owner confirms `DELETE ORGANIZATION`: CompatFlow first requests immediate cancellation of provider subscriptions, then removes every linked Supabase identity and cascades the organization, members, catalog records, import history, review records, local subscription/payment rows and related webhook history.
- If the payment provider cannot confirm cancellation, deletion is stopped before local organization data is removed.
- Supabase Auth and PostgreSQL cannot participate in one distributed transaction. If Supabase deletes some linked identities and then returns an error, retry deletion; already-absent identities are treated as deleted.
- Verify a recoverable backup and understand that this operation is irreversible before enabling the feature in a production environment.
