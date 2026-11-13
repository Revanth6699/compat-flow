from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

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
