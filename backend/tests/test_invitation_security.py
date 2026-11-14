from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import IntegrityError

from app.api import auth_routes
from app.core.auth import AuthenticatedUser, SupabaseIdentity, get_current_user, get_supabase_identity
from app.core.database import get_db
from app.main import app


class InvitationDB:
    def __init__(self, invitation):
        self.invitation = invitation
        self.scalar_calls = 0
        self.added = []
        self.committed = False

    def scalar(self, statement):
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return self.invitation
        return None

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def refresh(self, value):
        return None


def make_invitation(**overrides):
    values = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "email": "invited@example.com",
        "role": "member",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "accepted_at": None,
        "revoked_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def install_identity(identity, db):
    app.dependency_overrides[get_supabase_identity] = lambda: identity
    app.dependency_overrides[get_db] = lambda: db


def clear_overrides():
    app.dependency_overrides.clear()


def test_admin_cannot_invite_another_admin():
    profile = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        email="admin@example.com",
        role="admin",
        is_active=True,
    )
    current = AuthenticatedUser(
        identity=SupabaseIdentity(uuid4(), profile.email, "token"),
        profile=profile,
    )
    app.dependency_overrides[get_current_user] = lambda: current
    try:
        response = TestClient(app).post("/api/v1/invitations", json={
            "email": "new.admin@example.com",
            "role": "admin",
        })
        assert response.status_code == 403
    finally:
        clear_overrides()


def test_expired_invitation_cannot_be_accepted(monkeypatch):
    identity = SupabaseIdentity(uuid4(), "invited@example.com", "token")
    db = InvitationDB(make_invitation(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    install_identity(identity, db)
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)
    try:
        response = TestClient(app).post("/api/v1/invitations/accept", json={"token": "t" * 48})
        assert response.status_code == 400
        assert "expired" in response.json()["detail"]
        assert not db.committed
    finally:
        clear_overrides()


def test_revoked_invitation_cannot_be_accepted(monkeypatch):
    identity = SupabaseIdentity(uuid4(), "invited@example.com", "token")
    db = InvitationDB(make_invitation(revoked_at=datetime.now(timezone.utc)))
    install_identity(identity, db)
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)
    try:
        response = TestClient(app).post("/api/v1/invitations/accept", json={"token": "t" * 48})
        assert response.status_code == 400
        assert not db.committed
    finally:
        clear_overrides()


def test_previously_accepted_invitation_cannot_be_reused(monkeypatch):
    identity = SupabaseIdentity(uuid4(), "invited@example.com", "token")
    db = InvitationDB(make_invitation(accepted_at=datetime.now(timezone.utc)))
    install_identity(identity, db)
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)
    try:
        response = TestClient(app).post("/api/v1/invitations/accept", json={"token": "t" * 48})
        assert response.status_code == 400
        assert not db.committed
    finally:
        clear_overrides()


def test_invitation_cannot_be_accepted_by_different_email(monkeypatch):
    identity = SupabaseIdentity(uuid4(), "attacker@example.com", "token")
    db = InvitationDB(make_invitation())
    install_identity(identity, db)
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)
    try:
        response = TestClient(app).post("/api/v1/invitations/accept", json={"token": "t" * 48})
        assert response.status_code == 403
        assert not db.committed
    finally:
        clear_overrides()


def test_valid_invitation_is_consumed_once_and_creates_membership(monkeypatch):
    identity = SupabaseIdentity(uuid4(), "invited@example.com", "token")
    invitation = make_invitation()
    db = InvitationDB(invitation)
    install_identity(identity, db)
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)
    try:
        response = TestClient(app).post("/api/v1/invitations/accept", json={"token": "t" * 48})
        assert response.status_code == 200
        assert response.json()["organization_id"] == str(invitation.organization_id)
        assert invitation.accepted_at is not None
        assert db.committed
        assert len(db.added) == 1
        assert db.added[0].auth_user_id == identity.auth_user_id
    finally:
        clear_overrides()


def test_admin_cannot_revoke_an_administrator_invitation():
    profile = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        email="admin@example.com",
        role="admin",
        is_active=True,
    )
    current = AuthenticatedUser(
        identity=SupabaseIdentity(uuid4(), profile.email, "token"),
        profile=profile,
    )
    invitation = make_invitation(role="admin")
    db = InvitationDB(invitation)
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).delete(f"/api/v1/invitations/{invitation.id}")
        assert response.status_code == 403
        assert not db.committed
        assert invitation.revoked_at is None
    finally:
        clear_overrides()


class QueryCaptureDB:
    def __init__(self):
        self.statements = []
        self.committed = False

    def scalar(self, statement):
        self.statements.append(statement)
        return None

    def scalars(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: [])

    def commit(self):
        self.committed = True


def make_current(role="owner"):
    profile = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        email="owner@example.com",
        role=role,
        is_active=True,
    )
    return AuthenticatedUser(
        identity=SupabaseIdentity(uuid4(), profile.email, "token"),
        profile=profile,
    )


def test_invitation_list_query_is_scoped_to_current_organization():
    from sqlalchemy.dialects import postgresql

    current = make_current()
    db = QueryCaptureDB()
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).get("/api/v1/invitations")
        assert response.status_code == 200
        statement = db.statements[-1]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert current.profile.organization_id in compiled.params.values()
        assert "user_invitations.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_cannot_revoke_invitation_from_another_organization():
    from sqlalchemy.dialects import postgresql

    current = make_current()
    foreign_invitation_id = uuid4()
    db = QueryCaptureDB()
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).delete(f"/api/v1/invitations/{foreign_invitation_id}")
        assert response.status_code == 404
        statement = db.statements[-1]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert current.profile.organization_id in compiled.params.values()
        assert "user_invitations.organization_id" in str(compiled)
        assert db.committed is False
    finally:
        clear_overrides()


def test_postgres_invitation_lifecycle_and_cross_tenant_boundaries(monkeypatch):
    """Exercise invitation creation, listing, revocation, acceptance and reuse in PostgreSQL."""
    from app.core.database import SessionLocal
    from app.models import Organization, Subscription, SubscriptionPlan, User, UserInvitation

    db = SessionLocal()
    organization_a = Organization(name=f"Invite tenant A {uuid4().hex[:8]}")
    organization_b = Organization(name=f"Invite tenant B {uuid4().hex[:8]}")
    owner_a = User(
        organization_id=None,
        auth_user_id=uuid4(),
        email=f"invite-owner-a-{uuid4().hex[:8]}@example.test",
        role="owner",
        is_active=True,
        account_type="demo",
    )
    owner_b = User(
        organization_id=None,
        auth_user_id=uuid4(),
        email=f"invite-owner-b-{uuid4().hex[:8]}@example.test",
        role="owner",
        is_active=True,
        account_type="demo",
    )
    seat_plan = None
    try:
        db.add_all([organization_a, organization_b])
        db.flush()
        owner_a.organization_id = organization_a.id
        owner_b.organization_id = organization_b.id
        db.add_all([owner_a, owner_b])
        seat_plan = SubscriptionPlan(
            code=f"seat-{uuid4().hex[:8]}",
            name=f"Seat Test Plan {uuid4().hex[:8]}",
            entitlements={"member_seats": 2},
            is_active=True,
        )
        db.add(seat_plan)
        db.flush()
        db.add(Subscription(
            organization_id=organization_a.id,
            user_id=owner_a.id,
            plan_code=seat_plan.code,
            status="active",
        ))
        db.commit()

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            identity=SupabaseIdentity(owner_a.auth_user_id, owner_a.email, "owner-a-token"),
            profile=owner_a,
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)

        created_a = client.post("/api/v1/invitations", json={
            "email": f"new-member-a-{uuid4().hex[:8]}@example.com",
            "role": "member",
        })
        assert created_a.status_code == 201, created_a.text
        invitation_a = created_a.json()

        over_limit = client.post("/api/v1/invitations", json={
            "email": f"extra-member-{uuid4().hex[:8]}@example.com",
            "role": "viewer",
        })
        assert over_limit.status_code == 409, over_limit.text
        assert "member-seat limit" in over_limit.text

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            identity=SupabaseIdentity(owner_b.auth_user_id, owner_b.email, "owner-b-token"),
            profile=owner_b,
        )
        created_b = client.post("/api/v1/invitations", json={
            "email": f"new-member-b-{uuid4().hex[:8]}@example.com",
            "role": "viewer",
        })
        assert created_b.status_code == 201, created_b.text
        invitation_b = created_b.json()

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            identity=SupabaseIdentity(owner_a.auth_user_id, owner_a.email, "owner-a-token"),
            profile=owner_a,
        )
        listed_a = client.get("/api/v1/invitations")
        assert listed_a.status_code == 200, listed_a.text
        assert {row["id"] for row in listed_a.json()} == {invitation_a["id"]}
        foreign_revoke = client.delete(f"/api/v1/invitations/{invitation_b['id']}")
        assert foreign_revoke.status_code == 404

        invitee_identity = SupabaseIdentity(
            uuid4(), invitation_a["email"], "verified-invitee-token"
        )
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_supabase_identity] = lambda: invitee_identity
        monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)

        accepted = client.post("/api/v1/invitations/accept", json={
            "token": invitation_a["invitation_token"],
        })
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["organization_id"] == str(organization_a.id)
        assert accepted.json()["role"] == "member"

        reused = client.post("/api/v1/invitations/accept", json={
            "token": invitation_a["invitation_token"],
        })
        assert reused.status_code == 400

        stored_a = db.get(UserInvitation, invitation_a["id"])
        stored_b = db.get(UserInvitation, invitation_b["id"])
        assert stored_a is not None and stored_a.accepted_at is not None
        assert stored_b is not None and stored_b.revoked_at is None
    finally:
        clear_overrides()
        try:
            db.rollback()
            db.delete(organization_a)
            db.delete(organization_b)
            if seat_plan is not None:
                db.delete(seat_plan)
            db.commit()
        finally:
            db.close()


def test_postgres_rejects_cross_tenant_billing_inviter_and_import_lineage_links():
    """Database composite foreign keys must reject cross-organization references."""
    from app.core.database import SessionLocal
    from app.models import (
        ImportJob,
        ImportRecordLineage,
        Organization,
        Payment,
        Subscription,
        SubscriptionPlan,
        User,
        UserInvitation,
    )

    db = SessionLocal()
    organization_a = Organization(name=f"Integrity tenant A {uuid4().hex[:8]}")
    organization_b = Organization(name=f"Integrity tenant B {uuid4().hex[:8]}")
    plan = None
    try:
        db.add_all([organization_a, organization_b])
        db.flush()
        owner_a = User(
            organization_id=organization_a.id,
            auth_user_id=uuid4(),
            email=f"integrity-a-{uuid4().hex[:8]}@example.com",
            role="owner",
            is_active=True,
            account_type="demo",
        )
        owner_b = User(
            organization_id=organization_b.id,
            auth_user_id=uuid4(),
            email=f"integrity-b-{uuid4().hex[:8]}@example.com",
            role="owner",
            is_active=True,
            account_type="demo",
        )
        plan = SubscriptionPlan(
            code=f"integrity-{uuid4().hex[:8]}",
            name=f"Integrity Plan {uuid4().hex[:8]}",
            entitlements={},
            is_active=True,
        )
        db.add_all([owner_a, owner_b, plan])
        db.commit()

        # Persist the valid tenant fixtures before each expected constraint
        # violation; PostgreSQL rolls back the entire transaction on failure.
        bad_invitation = UserInvitation(
            organization_id=organization_a.id,
            email=f"cross-inviter-{uuid4().hex[:8]}@example.com",
            role="viewer",
            token_hash=uuid4().hex + uuid4().hex,
            invited_by_user_id=owner_b.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(bad_invitation)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        bad_subscription = Subscription(
            organization_id=organization_a.id,
            user_id=owner_b.id,
            plan_code=plan.code,
            status="active",
        )
        db.add(bad_subscription)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        valid_subscription = Subscription(
            organization_id=organization_a.id,
            user_id=owner_a.id,
            plan_code=plan.code,
            status="active",
        )
        db.add(valid_subscription)
        db.commit()

        bad_payment = Payment(
            organization_id=organization_a.id,
            user_id=owner_b.id,
            subscription_id=valid_subscription.id,
            provider="test",
            amount_minor=100,
            currency="USD",
            status="pending",
        )
        db.add(bad_payment)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        foreign_job = ImportJob(
            organization_id=organization_b.id,
            filename="foreign-tenant.csv",
        )
        db.add(foreign_job)
        db.commit()

        bad_lineage = ImportRecordLineage(
            organization_id=organization_a.id,
            job_id=foreign_job.id,
            record_type="products",
            source_location="row:1",
            target_record_id=uuid4(),
        )
        db.add(bad_lineage)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.rollback()
        db.delete(organization_a)
        db.delete(organization_b)
        if plan is not None:
            db.delete(plan)
        db.commit()
        db.close()
