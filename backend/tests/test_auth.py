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


def test_platform_owner_uses_system_record_safety_ceiling():
    from types import SimpleNamespace

    from app.core.auth import resolve_import_limits
    from app.core.config import settings

    current = SimpleNamespace(identity=SimpleNamespace(email=settings.platform_admin_email))
    limits = resolve_import_limits(current, db=None)
    assert limits["max_records"] == settings.import_max_records
    assert limits["max_upload_bytes"] == settings.import_max_upload_bytes


def test_paid_plan_record_quota_is_ignored_but_file_size_entitlement_is_enforced(monkeypatch):
    from types import SimpleNamespace

    from app.core import auth
    from app.core.config import settings

    current = SimpleNamespace(identity=SimpleNamespace(email="customer@example.com"))
    db = object()
    cases = [
        ("starter", 20_000, 10 * 1024 * 1024),
        ("growth", 40_000, 20 * 1024 * 1024),
        ("business", 100_000, 100 * 1024 * 1024),
    ]
    for plan_code, old_record_quota, max_upload_bytes in cases:
        plan = SimpleNamespace(
            code=plan_code,
            entitlements={
                "csv_validation": True,
                "upload_max_records": old_record_quota,
                "upload_max_bytes": max_upload_bytes,
            },
        )
        monkeypatch.setattr(auth, "get_active_plan", lambda _current, _db, p=plan: (object(), p))
        limits = auth.resolve_import_limits(current, db)
        assert limits["plan_code"] == plan_code
        assert limits["max_records"] == settings.import_max_records
        assert limits["max_upload_bytes"] == max_upload_bytes


def test_approved_demo_has_no_separate_record_quota(monkeypatch):
    from types import SimpleNamespace

    from app.core import auth
    from app.core.config import settings

    current = SimpleNamespace(identity=SimpleNamespace(email="demo@example.com"))
    monkeypatch.setattr(auth, "get_active_plan", lambda _current, _db: (None, None))

    class ApprovedDemoDb:
        def scalar(self, _query):
            return object()

    limits = auth.resolve_import_limits(current, ApprovedDemoDb())
    assert limits["access_type"] == "demo"
    assert limits["max_records"] == settings.import_max_records
    assert limits["max_upload_bytes"] == 5 * 1024 * 1024

def test_paid_plan_upload_limits_come_from_active_plan_entitlements(monkeypatch):
    from types import SimpleNamespace

    from app.core import auth

    current = SimpleNamespace(identity=SimpleNamespace(email="customer@example.com"))
    db = object()
    cases = [
        ("starter", 20_000, 10 * 1024 * 1024),
        ("growth", 40_000, 20 * 1024 * 1024),
        ("business", 100_000, 100 * 1024 * 1024),
    ]
    for plan_code, max_records, max_upload_bytes in cases:
        plan = SimpleNamespace(
            code=plan_code,
            entitlements={
                "csv_validation": True,
                "upload_max_records": max_records,
                "upload_max_bytes": max_upload_bytes,
            },
        )
        monkeypatch.setattr(auth, "get_active_plan", lambda _current, _db, p=plan: (object(), p))
        limits = auth.resolve_import_limits(current, db)
        assert limits["plan_code"] == plan_code
        assert limits["max_records"] == max_records
        assert limits["max_upload_bytes"] == max_upload_bytes


def test_approved_demo_upload_limits_remain_ten_thousand_and_five_mb(monkeypatch):
    from types import SimpleNamespace

    from app.core import auth

    current = SimpleNamespace(identity=SimpleNamespace(email="demo@example.com"))
    monkeypatch.setattr(auth, "get_active_plan", lambda _current, _db: (None, None))

    class ApprovedDemoDb:
        def scalar(self, _query):
            return object()

    limits = auth.resolve_import_limits(current, ApprovedDemoDb())
    assert limits["access_type"] == "demo"
    assert limits["max_records"] == 10_000
    assert limits["max_upload_bytes"] == 5 * 1024 * 1024
