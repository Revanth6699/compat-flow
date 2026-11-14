import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
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
