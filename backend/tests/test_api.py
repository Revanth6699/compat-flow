import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_readiness_returns_ok_when_database_query_succeeds():
    from app.core.database import get_db

    class HealthyDatabase:
        def execute(self, statement):
            assert str(statement) == "SELECT 1"

    app.dependency_overrides[get_db] = lambda: HealthyDatabase()
    try:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "ok"}
    finally:
        app.dependency_overrides.clear()


def test_readiness_returns_503_when_database_query_fails():
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.database import get_db

    class UnavailableDatabase:
        def execute(self, statement):
            raise SQLAlchemyError("connection failed")

    app.dependency_overrides[get_db] = lambda: UnavailableDatabase()
    try:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["detail"] == "Database is unavailable."
    finally:
        app.dependency_overrides.clear()



@pytest.mark.parametrize(
    ("path", "filename", "payload", "content_type"),
    [
        ("/api/v1/catalog/import/profile", "dataset.csv", b"a,b\n1,2\n", "text/csv"),
        ("/api/v1/catalog/import/preview", "catalog.csv", b"sku,name\nS1,Brake\n", "text/csv"),
        ("/api/v1/catalog/import/preview-records", "catalog.xlsx", b"not-a-workbook", "application/octet-stream"),
        ("/api/v1/catalog/import/validate", "catalog.csv", b"sku,name\nS1,Brake\n", "text/csv"),
        ("/api/v1/catalog/import/validate-records", "catalog.csv", b"sku,name\nS1,Brake\n", "text/csv"),
    ],
)
def test_all_upload_and_preview_routes_require_authenticated_authorized_access(path, filename, payload, content_type):
    response = client.post(path, files={"file": (filename, payload, content_type)})
    assert response.status_code == 401


def test_persistent_import_is_disabled():
    response = client.post(
        "/api/v1/catalog/import",
        files={"file": ("catalog.csv", b"sku,name\nSKU-1,Brake Pad\n", "text/csv")},
    )
    assert response.status_code == 403


def test_import_job_status_endpoint_is_not_exposed():
    response = client.get("/api/v1/catalog/import/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


def test_preview_rejects_upload_over_configured_limit_before_auth():
    oversized = b"x" * (26 * 1024 * 1024)
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("large.csv", oversized, "text/csv")},
    )
    assert response.status_code == 413


def test_platform_owner_can_validate_more_than_ten_thousand_rows(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from app.api import routes
    from app.core.auth import AuthenticatedUser, SupabaseIdentity, get_current_user
    from app.core.config import settings
    from app.core.database import get_db

    owner_email = settings.platform_admin_email.split(",")[0].strip().lower()
    owner = AuthenticatedUser(
        identity=SupabaseIdentity(
            auth_user_id=uuid4(), email=owner_email, access_token="test-owner-token"
        ),
        profile=SimpleNamespace(role="admin"),
    )
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_db] = lambda: None
    monkeypatch.setattr(
        routes,
        "validate_industry_records",
        lambda headers, rows, profile_id=None: {"total_rows": len(rows)},
    )
    csv_data = ("sku\n" + "".join(f"SKU-{index}\n" for index in range(10_001))).encode()

    try:
        response = client.post(
            "/api/v1/catalog/import/validate-industry",
            files={"file": ("large-catalog.csv", csv_data, "text/csv")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["total_rows"] == 10_001
    finally:
        app.dependency_overrides.clear()
