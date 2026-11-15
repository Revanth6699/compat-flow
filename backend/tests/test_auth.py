from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_current_user_requires_bearer_token():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_invitation_creation_requires_authenticated_admin():
    response = client.post(
        "/api/v1/invitations",
        json={"email": "new.member@example.com", "role": "member"},
    )
    assert response.status_code == 401


def test_invitation_listing_requires_authenticated_admin():
    response = client.get("/api/v1/invitations")
    assert response.status_code == 401


def test_invitation_acceptance_requires_supabase_identity():
    response = client.post(
        "/api/v1/invitations/accept",
        json={"token": "x" * 48},
    )
    assert response.status_code == 401


def test_invitation_revocation_requires_authenticated_admin():
    response = client.delete(
        "/api/v1/invitations/00000000-0000-0000-0000-000000000001"
    )
    assert response.status_code == 401
