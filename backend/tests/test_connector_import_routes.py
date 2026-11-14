import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace
from uuid import uuid4

from app.main import app
from app.core.config import settings
from app.core.auth import AuthenticatedUser, SupabaseIdentity, get_current_user
from app.core.database import get_db
from app.api import connector_import_routes as routes
from app.api.connector_import_routes import ConnectorImportRequest, _prepare, _require_allowed_host

client = TestClient(app)


def test_connector_routes_require_authentication():
    payload = {
        "source_type": "rest_api",
        "record_type": "products",
        "api_url": "https://supplier.example/catalog",
    }
    assert client.post("/api/v1/catalog/import/connectors/preview", json=payload).status_code == 401
    assert client.post("/api/v1/catalog/import/connectors/commit", json=payload).status_code == 401
    assert client.get("/api/v1/catalog/import/history").status_code == 401


def test_import_history_detail_does_not_expose_other_tenants_without_auth():
    response = client.get("/api/v1/catalog/import/history/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 401


def test_connector_host_must_be_explicitly_allowlisted(monkeypatch):
    monkeypatch.setattr(settings, "connector_allowed_hosts", "supplier.example,files.example")
    assert _require_allowed_host("SUPPLIER.EXAMPLE.") == "supplier.example"
    with pytest.raises(Exception, match="CONNECTOR_ALLOWED_HOSTS"):
        _require_allowed_host("attacker.example")


def test_connector_file_pipeline_runs_parse_and_deterministic_validation():
    payload = ConnectorImportRequest(
        source_type="rest_api",
        record_type="products",
        column_mapping=None,
    )
    raw = b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]'
    parsed, result = _prepare(payload, raw, "supplier.json")
    assert parsed.format == "json"
    assert result.total_records == 1
    assert len(result.valid_records) == 1
    assert result.valid_records[0]["sku"] == "001"


def test_connector_pipeline_rejects_bad_record_type():
    with pytest.raises(ValueError):
        ConnectorImportRequest(source_type="rest_api", record_type="untrusted_type")


class ConnectorRouteDB:
    def __init__(self, permission_granted=True):
        self.permission_granted = permission_granted
        self.subscription = SimpleNamespace(status="active")
        self.plan = SimpleNamespace(code="growth", is_active=True, entitlements={"supplier_catalogs": True})

    def scalar(self, statement):
        return object() if self.permission_granted else None

    def get(self, model, key):
        return self.plan


def install_connector_auth(monkeypatch, permission_granted=True):
    organization_id = uuid4()
    profile = SimpleNamespace(
        id=uuid4(), organization_id=organization_id, role="member",
        email="member@example.com", is_active=True,
    )
    identity = SupabaseIdentity(
        auth_user_id=uuid4(), email="member@example.com", access_token="test-token",
    )
    current = AuthenticatedUser(identity=identity, profile=profile)
    db = ConnectorRouteDB(permission_granted=permission_granted)
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: db
    return organization_id, current, db


def clear_connector_auth():
    app.dependency_overrides.clear()


def test_authenticated_connector_preview_runs_validation_without_persisting(monkeypatch):
    organization_id, _, _ = install_connector_auth(monkeypatch)
    async def fake_load_source(payload):
        return (
            b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]',
            "supplier.json",
        )
    monkeypatch.setattr(routes, "_load_source", fake_load_source)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/connectors/preview",
            json={"source_type": "rest_api", "record_type": "products", "api_url": "https://supplier.example/catalog"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_records"] == 1
        assert data["valid_records"] == 1
        assert data["persisted"] is False
    finally:
        clear_connector_auth()


def test_authenticated_connector_commit_persists_for_authenticated_tenant(monkeypatch):
    organization_id, _, _ = install_connector_auth(monkeypatch)
    calls = {}
    async def fake_load_source(payload):
        return (
            b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]',
            "supplier.json",
        )
    def fake_persist(**kwargs):
        calls.update(kwargs)
        return {"status": "completed", "imported_records": 1}
    monkeypatch.setattr(routes, "_load_source", fake_load_source)
    monkeypatch.setattr(routes, "persist_validated_import", fake_persist)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/connectors/commit",
            json={"source_type": "rest_api", "record_type": "products", "api_url": "https://supplier.example/catalog"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "completed"
        assert calls["organization_id"] == organization_id
    finally:
        clear_connector_auth()


def test_connector_preview_rejects_user_without_catalog_read_permission(monkeypatch):
    install_connector_auth(monkeypatch, permission_granted=False)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/connectors/preview",
            json={"source_type": "rest_api", "record_type": "products", "api_url": "https://supplier.example/catalog"},
        )
        assert response.status_code == 403
    finally:
        clear_connector_auth()
