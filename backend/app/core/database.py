from __future__ import annotations

from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

_RLS_AUTH_USER_KEY = "rls_auth_user_id"
_RLS_ORGANIZATION_KEY = "rls_organization_id"


def set_rls_identity(db: Session, auth_user_id: UUID) -> None:
    """Bind a verified Supabase subject to this request-scoped SQLAlchemy session."""
    value = str(auth_user_id)
    existing = db.info.get(_RLS_AUTH_USER_KEY)
    if existing is not None and existing != value:
        raise RuntimeError("A database session cannot be reused for another authenticated identity.")
    db.info[_RLS_AUTH_USER_KEY] = value
    _apply_rls_context(db)


def set_rls_organization(db: Session, organization_id: UUID) -> None:
    """Bind the organization resolved from the trusted CompatFlow user record."""
    value = str(organization_id)
    existing = db.info.get(_RLS_ORGANIZATION_KEY)
    if existing is not None and existing != value:
        raise RuntimeError("A database session cannot be rebound to another organization.")
    if _RLS_AUTH_USER_KEY not in db.info:
        raise RuntimeError("Resolve a verified Supabase identity before setting organization context.")
    db.info[_RLS_ORGANIZATION_KEY] = value
    _apply_rls_context(db)


def _apply_rls_context(db: Session) -> None:
    """Apply settings immediately when a transaction is already active."""
    if db.get_bind().dialect.name != "postgresql" or not db.in_transaction():
        return
    db.execute(
        text("SELECT set_config('app.auth_user_id', :auth_user_id, true)"),
        {"auth_user_id": db.info.get(_RLS_AUTH_USER_KEY, "")},
    )
    db.execute(
        text("SELECT set_config('app.organization_id', :organization_id, true)"),
        {"organization_id": db.info.get(_RLS_ORGANIZATION_KEY, "")},
    )


@event.listens_for(Session, "after_begin")
def _restore_rls_context(session: Session, transaction, connection) -> None:
    """Restore request identity after every new transaction, including post-commit."""
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        text("SELECT set_config('app.auth_user_id', :auth_user_id, true)"),
        {"auth_user_id": session.info.get(_RLS_AUTH_USER_KEY, "")},
    )
    connection.execute(
        text("SELECT set_config('app.organization_id', :organization_id, true)"),
        {"organization_id": session.info.get(_RLS_ORGANIZATION_KEY, "")},
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
