# Backend operations

## Connector credential encryption

Set `CONNECTOR_CREDENTIAL_ENCRYPTION_KEY` on every backend instance before using saved connector configurations. It must be URL-safe base64 encoding of exactly 32 cryptographically random bytes. Generate it securely outside the application, store it only in the deployment secret manager, and use the same value across all instances that access the same database. Do not commit it or derive it from `APP_SECRET_KEY`.

The application encrypts connector credentials with AES-256-GCM and binds each ciphertext to its organization, configuration ID, and source type. Missing/invalid keys cause saved-configuration creation or use to fail closed. Back up the key separately from the database. Key rotation/re-encryption is not implemented yet; replacing the key without re-encrypting existing rows will make those saved credentials unavailable.

Saved configurations can be created only for allowlisted REST API, SFTP, and SQL Server sources. The API returns source settings and a sanitized descriptor, never ciphertext or decrypted credentials. Keep the SQL Server login read-only at the database permission layer; `ApplicationIntent=ReadOnly` is not a substitute.


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

Connector preview and commit routes require the existing supplier_catalogs plan entitlement and a database-backed catalog:read or catalog:write permission. Redis enforces a fixed-window per-organization request limit; if Redis is unavailable, connector execution fails closed. Import history stores source type, a sanitized source descriptor, non-secret source metadata, row errors, and record lineage. Inline API tokens, SFTP passwords/private keys, and SQL Server connection URLs are request-scoped and must never enter import metadata, errors, or logs. Explicitly saved configurations persist only AES-256-GCM ciphertext in the organization-scoped connector vault; plaintext credentials are never returned by its API.

### SQL Server runtime requirement

The backend Dockerfile installs Microsoft ODBC Driver 18 for SQL Server and verifies its registration through pyodbc.drivers() during image build. The runtime connector also checks that the driver exists before connecting. The deployment operator must confirm that the deployed service actually uses the repository Dockerfile. Python package installation alone does not install the Microsoft ODBC driver.

Provision a dedicated SQL-authenticated login with only SELECT on the approved schema/table/view. Use Encrypt=yes, TrustServerCertificate=no, and ApplicationIntent=ReadOnly; the latter is not a substitute for database permissions. Do not enable SQL Server ingestion until a real test connection and permission-boundary test pass.

### Connector credential handling

Saved connector configurations are organization-scoped and encrypted with AES-256-GCM. `CONNECTOR_CREDENTIAL_ENCRYPTION_KEY` is the active 32-byte URL-safe base64 key; `CONNECTOR_CREDENTIAL_ENCRYPTION_KEY_VERSION` identifies it (default `v1`). During rotation, set a new active key and increment its version, then retain prior keys in `CONNECTOR_CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS` as a JSON object mapping versions to URL-safe base64 keys. Keep every old key configured until all affected configurations have been re-encrypted. Use `POST /api/v1/catalog/import/connectors/configurations/{id}/rotate-credentials` for each saved configuration; it re-encrypts atomically and records a secret-free audit event. Inspect events with `GET /api/v1/catalog/import/connectors/configurations/{id}/audit`. Removing an old key before all configurations are rotated makes those credentials unreadable. The API never returns plaintext or ciphertext. Inline credentials remain request-scoped. Do not add secrets to import metadata, mapping templates, or error messages. SFTP known-hosts must be mounted as a managed file; do not accept host keys from the client.

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
