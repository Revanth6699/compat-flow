import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
    oversized = b"x" * (25 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("large.csv", oversized, "text/csv")},
    )
    assert response.status_code == 413
