import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from types import SimpleNamespace

import app.core.auth as auth_module

from app.api.auth_routes import _require_supabase_admin_configured
from app.core.config import settings

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


def test_deletion_preflight_requires_supabase_admin_credential(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    with pytest.raises(HTTPException) as error:
        _require_supabase_admin_configured()
    assert error.value.status_code == 503
    assert "admin credential is not configured" in error.value.detail


def test_deletion_preflight_returns_configured_supabase_admin_credential(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "test-admin-secret")
    assert _require_supabase_admin_configured() == "test-admin-secret"



def test_deleted_supabase_identity_cannot_reuse_an_unexpired_jwt(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "test-anon-key")
    monkeypatch.setattr(
        auth_module.jwt, "get_unverified_header", lambda token: {"alg": "RS256"}
    )
    monkeypatch.setattr(
        auth_module, "_jwks_client",
        lambda: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="test-key")),
    )
    monkeypatch.setattr(
        auth_module.jwt, "decode",
        lambda *args, **kwargs: {
            "sub": "00000000-0000-0000-0000-000000000123",
            "email": "deleted@example.com",
        },
    )
    monkeypatch.setattr(
        auth_module.httpx, "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=404),
    )

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-but-deleted-jwt")
    with pytest.raises(HTTPException) as error:
        auth_module.get_supabase_identity(credentials)

    assert error.value.status_code == 401


def test_supabase_identity_requires_live_user_match(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "test-anon-key")
    monkeypatch.setattr(
        auth_module.jwt, "get_unverified_header", lambda token: {"alg": "RS256"}
    )
    monkeypatch.setattr(
        auth_module, "_jwks_client",
        lambda: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="test-key")),
    )
    monkeypatch.setattr(
        auth_module.jwt, "decode",
        lambda *args, **kwargs: {
            "sub": "00000000-0000-0000-0000-000000000123",
            "email": "new@example.com",
        },
    )
    monkeypatch.setattr(
        auth_module.httpx, "get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "id": "00000000-0000-0000-0000-000000000123",
                "email": "new@example.com",
            },
        ),
    )

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-live-jwt")
    identity = auth_module.get_supabase_identity(credentials)

    assert str(identity.auth_user_id) == "00000000-0000-0000-0000-000000000123"
    assert identity.email == "new@example.com"
