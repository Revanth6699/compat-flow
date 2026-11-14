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



def test_member_directory_requires_authenticated_admin():
    response = client.get("/api/v1/invitations/members")
    assert response.status_code == 401


def test_member_access_update_requires_authenticated_admin():
    response = client.patch(
        "/api/v1/invitations/members/00000000-0000-0000-0000-000000000001",
        json={"role": "viewer"},
    )
    assert response.status_code == 401



def test_account_deletion_requires_authenticated_supabase_identity():
    response = client.request(
        "DELETE",
        "/api/v1/auth/account",
        json={"confirmation": "DELETE MY ACCOUNT"},
    )
    assert response.status_code == 401


def test_review_submission_requires_authenticated_user():
    response = client.post(
        "/api/v1/reviews/mine",
        json={"display_name": "Example User", "rating": 5, "comment": "This is a sufficiently detailed review."},
    )
    assert response.status_code == 401


def test_demo_access_status_requires_authenticated_account():
    response = client.get("/api/v1/demo-requests/mine")
    assert response.status_code == 401


def test_platform_admin_overview_requires_authenticated_account():
    response = client.get("/api/v1/platform-admin/overview")
    assert response.status_code == 401


def test_platform_admin_demo_request_queue_requires_authenticated_account():
    response = client.get("/api/v1/platform-admin/demo-requests")
    assert response.status_code == 401
