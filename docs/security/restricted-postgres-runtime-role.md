# Restricted PostgreSQL runtime role rollout

The API and workers connect as a non-owner role subject to forced row-level security (RLS). Alembic and role provisioning use the database-owner connection only during an explicitly enabled release migration.

## Environment configuration

Set these variables on the backend service:

- `RUNTIME_DATABASE_ROLE`: `compatflow_runtime` (or another simple PostgreSQL role name).
- `RUNTIME_DATABASE_PASSWORD`: a newly generated strong password stored only as a Render secret.
- `STAGING_AUTO_MIGRATE=true` for staging or `PRODUCTION_AUTO_MIGRATE=true` for production when intentionally applying the migration release.

`MIGRATION_DATABASE_URL` is the preferred explicit owner connection string. If it is omitted, the entrypoint treats the existing `DATABASE_URL` as the owner connection for the migration step, derives a separate runtime URL by replacing its role and password, preserves a Supabase pooler project-ref username suffix when present, and exports that runtime URL before starting the API. This supports a production service that currently has only its owner `DATABASE_URL` configured without copying the database secret into a second environment variable.

If both `MIGRATION_DATABASE_URL` and `DATABASE_URL` are supplied, they must be different connections. `DATABASE_URL` must authenticate as the restricted runtime role; `MIGRATION_DATABASE_URL` must authenticate as the owner/migration role.

Do not copy database credentials into Git, tickets, or chat.

## Startup behavior

When the staging or production auto-migration flag is explicitly enabled, the entrypoint:

1. Keeps the owner URL in `MIGRATION_DATABASE_URL` and derives the restricted `DATABASE_URL` if needed.
2. Runs `alembic upgrade head` through the migration connection.
3. Provisions/reconciles the runtime role with only schema usage, table DML, and sequence usage/select.
4. Starts Uvicorn with the restricted `DATABASE_URL`.

The API engine uses `DATABASE_URL` only. The migration connection is not used by request handlers. If migration or role provisioning fails, the API process does not start.

## Promotion gates

Before enabling production migration, verify the exact production database target and take a restorable backup. After deployment:

1. Confirm `current_user` in an API DB connection is `compatflow_runtime`, not the table owner.
2. Confirm `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, and `rolbypassrls` are all false.
3. Confirm the runtime role is not a table owner and has no inherited role memberships.
4. Confirm it has no TRUNCATE, REFERENCES, TRIGGER, CREATE, or ALTER privileges.
5. Run authenticated two-tenant SELECT/INSERT/UPDATE/DELETE isolation tests, plus onboarding, invitations, import workers, reviews, demo requests, and verified payment webhook paths.
6. Verify ordinary restart and health checks after migration.

The provisioning script is idempotent for role attributes and grants. It refuses to run when the runtime role name equals the migration owner or when the role inherits other roles. It does not transfer table ownership.
