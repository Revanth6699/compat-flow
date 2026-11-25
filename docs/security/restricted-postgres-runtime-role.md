# Restricted PostgreSQL runtime role rollout

The API and workers must connect as a non-owner role subject to forced RLS. Alembic must connect separately as the database/table owner.

## Required Render environment configuration (staging first)

- `MIGRATION_DATABASE_URL`: current staging owner connection string. Keep this secret restricted to the backend service that runs migrations.
- `RUNTIME_DATABASE_ROLE`: `compatflow_runtime` (or another simple PostgreSQL role name).
- `RUNTIME_DATABASE_PASSWORD`: a newly generated strong password stored only in Render environment secrets.
- `DATABASE_URL`: connection string for that runtime role, using the same password and database/host as the migration URL.

Do not set `DATABASE_URL` equal to `MIGRATION_DATABASE_URL`. Do not copy credentials into Git, tickets, or chat.

## Startup behavior

When explicit staging/production auto-migration is enabled, the entrypoint runs Alembic through `MIGRATION_DATABASE_URL`, then provisions or reconciles the restricted role and grants only schema usage, table DML, and sequence usage/select. It denies TRUNCATE/REFERENCES/TRIGGER and ensures the role has no superuser, database creation, role creation, replication, BYPASSRLS, or inherited-role attributes.

The API engine continues to use `DATABASE_URL` only. The migration connection is not used by request handlers.

## Staging validation gate

After setting the four environment variables on staging and deploying:

1. Confirm `current_user` in an API DB connection is the runtime role, not the table owner.
2. Confirm `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, and `rolbypassrls` are all false.
3. Confirm the runtime role is not a table owner and has no inherited role memberships.
4. Confirm it has no TRUNCATE, REFERENCES, TRIGGER, CREATE, or ALTER privileges.
5. Run authenticated two-tenant SELECT/INSERT/UPDATE/DELETE integration tests, plus onboarding, invitations, import workers, reviews, demo requests, and verified payment webhook paths.
6. Exercise migration startup and an ordinary restart. Do not promote to production until all tests pass.

The provisioning script is intentionally idempotent for role attributes and grants. It refuses to run when the runtime role name equals the migration owner or when the role inherits other roles. It does not transfer table ownership.
