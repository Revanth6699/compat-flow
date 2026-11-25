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

_RLS_CONTEXT_KEYS = {
    "app.auth_user_id": "rls_auth_user_id",
    "app.organization_id": "rls_organization_id",
    "app.user_email": "rls_user_email",
    "app.is_platform_admin": "rls_is_platform_admin",
    "app.allow_demo_request_insert": "rls_allow_demo_request_insert",
    "app.allow_onboarding": "rls_allow_onboarding",
    "app.verified_payment_webhook": "rls_verified_payment_webhook",
    "app.is_worker": "rls_is_worker",
}


def _set_context(db: Session, setting: str, value: str, *, immutable: bool = True) -> None:
    key = _RLS_CONTEXT_KEYS[setting]
    existing = db.info.get(key)
    if immutable and existing is not None and existing != value:
        raise RuntimeError(f"Database context {setting} cannot be rebound within a session.")
    db.info[key] = value
    _apply_rls_context(db)


def set_rls_identity(db: Session, auth_user_id: UUID) -> None:
    """Bind a verified Supabase subject to this request-scoped SQLAlchemy session."""
    _set_context(db, "app.auth_user_id", str(auth_user_id))


def set_rls_organization(db: Session, organization_id: UUID) -> None:
    """Bind the organization resolved from the trusted CompatFlow user record."""
    if "rls_auth_user_id" not in db.info:
        raise RuntimeError("Resolve a verified Supabase identity before setting organization context.")
    _set_context(db, "app.organization_id", str(organization_id))


def set_rls_user_email(db: Session, email: str) -> None:
    _set_context(db, "app.user_email", email.strip().lower())


def set_rls_platform_admin(db: Session, is_admin: bool) -> None:
    _set_context(db, "app.is_platform_admin", "true" if is_admin else "false")


def set_rls_public_demo_request(db: Session, email: str) -> None:
    """Permit this request to create/read only its own public demo request."""
    set_rls_user_email(db, email)
    _set_context(db, "app.allow_demo_request_insert", "true")


def set_rls_onboarding(db: Session) -> None:
    """Permit a verified, not-yet-linked identity to create its initial tenant."""
    if "rls_auth_user_id" not in db.info:
        raise RuntimeError("Verified identity is required for organization onboarding.")
    _set_context(db, "app.allow_onboarding", "true")


def set_rls_verified_payment_webhook(db: Session) -> None:
    """Permit payment webhook writes only after the provider signature is verified."""
    _set_context(db, "app.verified_payment_webhook", "true")


def set_rls_worker_organization(db: Session, organization_id: UUID) -> None:
    """Bind a trusted internal worker task to the tenant carried by its queue message."""
    _set_context(db, "app.organization_id", str(organization_id))
    _set_context(db, "app.is_worker", "true")


def _apply_rls_context(db: Session) -> None:
    """Apply transaction-local settings immediately when a transaction is active."""
    if db.get_bind().dialect.name != "postgresql" or not db.in_transaction():
        return
    for setting, key in _RLS_CONTEXT_KEYS.items():
        db.execute(
            text("SELECT set_config(:setting, :value, true)"),
            {"setting": setting, "value": db.info.get(key, "")},
        )


@event.listens_for(Session, "after_begin")
def _restore_rls_context(session: Session, transaction, connection) -> None:
    """Restore request identity after every new transaction, including post-commit."""
    if connection.dialect.name != "postgresql":
        return
    for setting, key in _RLS_CONTEXT_KEYS.items():
        connection.execute(
            text("SELECT set_config(:setting, :value, true)"),
            {"setting": setting, "value": session.info.get(key, "")},
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
