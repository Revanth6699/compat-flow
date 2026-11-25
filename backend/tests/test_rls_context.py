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


def test_rls_identity_is_bound_to_session_info(db):
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
    set_rls_organization(db, UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    with pytest.raises(RuntimeError, match="cannot be rebound"):
        set_rls_organization(db, UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"))


def test_new_transaction_restores_both_transaction_local_settings():
    from types import SimpleNamespace
    from app.core.database import _restore_rls_context

    calls = []

    class FakeConnection:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, parameters):
            calls.append((str(statement), parameters))

    session = SimpleNamespace(info={
        "rls_auth_user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "rls_organization_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    })
    _restore_rls_context(session, transaction=None, connection=FakeConnection())

    assert len(calls) == 2
    assert "app.auth_user_id" in calls[0][0]
    assert calls[0][1]["auth_user_id"] == session.info["rls_auth_user_id"]
    assert "app.organization_id" in calls[1][0]
    assert calls[1][1]["organization_id"] == session.info["rls_organization_id"]


def test_new_transaction_clears_unset_tenant_context():
    from types import SimpleNamespace
    from app.core.database import _restore_rls_context

    calls = []

    class FakeConnection:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, parameters):
            calls.append(parameters)

    _restore_rls_context(SimpleNamespace(info={}), transaction=None, connection=FakeConnection())
    assert calls == [{"auth_user_id": ""}, {"organization_id": ""}]


def test_postgres_context_survives_commit_and_new_transaction():
    from sqlalchemy import text

    from app.core.database import SessionLocal, engine

    if engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL transaction-local settings.")

    auth_user_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    organization_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    db = SessionLocal()
    try:
        set_rls_identity(db, auth_user_id)
        set_rls_organization(db, organization_id)

        before_commit = db.execute(
            text("SELECT current_setting('app.auth_user_id', true), current_setting('app.organization_id', true)")
        ).one()
        assert before_commit == (str(auth_user_id), str(organization_id))

        db.commit()

        after_commit = db.execute(
            text("SELECT current_setting('app.auth_user_id', true), current_setting('app.organization_id', true)")
        ).one()
        assert after_commit == (str(auth_user_id), str(organization_id))
    finally:
        db.rollback()
        db.close()
