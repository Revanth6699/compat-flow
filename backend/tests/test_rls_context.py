from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import set_rls_identity, set_rls_organization


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_rls_identity_is_bound_to_session_info_without_requiring_connection(db):
    identity = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    set_rls_identity(db, identity)
    assert db.info["rls_auth_user_id"] == str(identity)
    assert "rls_organization_id" not in db.info


def test_rls_identity_cannot_be_switched_within_a_session(db):
    set_rls_identity(db, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    with pytest.raises(RuntimeError, match="cannot be reused"):
        set_rls_identity(db, UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))


def test_organization_context_requires_verified_identity_first(db):
    with pytest.raises(RuntimeError, match="verified Supabase identity"):
        set_rls_organization(db, UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))


def test_organization_context_cannot_be_switched_within_a_session(db):
    set_rls_identity(db, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    first = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    set_rls_organization(db, first)
    with pytest.raises(RuntimeError, match="cannot be rebound"):
        set_rls_organization(db, UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"))
