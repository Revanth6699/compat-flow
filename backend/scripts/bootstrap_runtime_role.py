"""Provision a non-owner, non-bypass PostgreSQL login for application traffic.

Run only with MIGRATION_DATABASE_URL pointing at the database owner connection.
The runtime password is supplied through the deployment secret RUNTIME_DATABASE_PASSWORD.
"""
from __future__ import annotations

import os
import re

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def main() -> None:
    raw_url = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    role = os.environ.get("RUNTIME_DATABASE_ROLE", "compatflow_runtime").strip()
    password = os.environ.get("RUNTIME_DATABASE_PASSWORD", "")
    if not raw_url or not password:
        raise SystemExit("MIGRATION_DATABASE_URL and RUNTIME_DATABASE_PASSWORD are required.")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise SystemExit("RUNTIME_DATABASE_ROLE must be a simple PostgreSQL identifier.")
    conninfo = make_url(raw_url).set(drivername="postgresql").render_as_string(hide_password=False)

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database()")
            owner, database = cur.fetchone()
            if role == owner:
                raise SystemExit("Runtime role must not be the migration/database owner.")
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            exists = cur.fetchone() is not None
            role_ddl = sql.SQL(
                "ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(role), sql.Literal(password))
            if exists:
                cur.execute(role_ddl)
            else:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(password))
                )

            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), sql.Identifier(role)
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role))
            )
            cur.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                ).format(sql.Identifier(role))
            )
            cur.execute(
                sql.SQL("REVOKE TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM {}").format(
                    sql.Identifier(role)
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                    sql.Identifier(role)
                )
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(sql.Identifier(owner), sql.Identifier(role))
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT USAGE, SELECT ON SEQUENCES TO {}"
                ).format(sql.Identifier(owner), sql.Identifier(role))
            )
            cur.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (role,),
            )
            flags = cur.fetchone()
            if flags != (False, False, False, False, False):
                raise RuntimeError(f"Runtime role retains elevated attributes: {flags!r}")
            cur.execute(
                "SELECT count(*) FROM pg_auth_members m "
                "JOIN pg_roles r ON r.oid = m.roleid "
                "JOIN pg_roles u ON u.oid = m.member "
                "WHERE u.rolname = %s",
                (role,),
            )
            memberships = cur.fetchone()[0]
            if memberships:
                raise RuntimeError(
                    "Runtime role has inherited role memberships; remove/review them before use."
                )
        conn.commit()
    print(f"Provisioned restricted PostgreSQL runtime role {role!r} on {database!r}.")


if __name__ == "__main__":
    main()
