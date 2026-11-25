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


async def _async_noop():
    return None


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
        self.subscription = SimpleNamespace(status="active", plan_code="growth", current_period_end=None)
        self.plan = SimpleNamespace(code="growth", is_active=True, entitlements={"supplier_catalogs": True})

    def scalar(self, statement):
        if not self.permission_granted:
            return None
        entity = statement.column_descriptions[0].get("entity")
        if getattr(entity, "__name__", None) == "Subscription":
            return self.subscription
        return object()

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
    _, _, _ = install_connector_auth(monkeypatch)
    async def fake_load_source(payload):
        return (
            b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]',
            "supplier.json",
        )
    monkeypatch.setattr(routes, "_load_source", fake_load_source)
    monkeypatch.setattr(routes, "_enforce_connector_rate_limit", lambda organization_id: _async_noop())
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
    monkeypatch.setattr(routes, "_enforce_connector_rate_limit", lambda organization_id: _async_noop())
    monkeypatch.setattr(routes, "persist_validated_import", fake_persist)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/connectors/commit",
            json={"source_type": "rest_api", "record_type": "products", "api_url": "https://supplier.example/catalog"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "completed"
        assert calls["organization_id"] == organization_id
        assert calls["source_type"] == "rest_api"
        assert calls["source_descriptor"] == "https://supplier.example"
        assert calls["source_metadata"]["pagination"]["mode"] == "single_page"
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



def test_connector_source_descriptors_never_include_credentials_or_query_tokens():
    api = ConnectorImportRequest(
        source_type="rest_api",
        record_type="products",
        api_url="https://reader:secret@supplier.example/catalog?api_key=hidden",
    )
    assert routes._source_descriptor(api) == "https://supplier.example"

    sql = ConnectorImportRequest(
        source_type="sql_server",
        record_type="products",
        sql_server_url="mssql+pyodbc://reader:secret@sql.example/catalog?password=hidden",
        sql_schema="dbo",
        sql_table="Products",
    )
    descriptor = routes._source_descriptor(sql)
    assert descriptor == "sqlserver://sql.example/catalog/dbo.Products"
    assert "secret" not in descriptor and "hidden" not in descriptor


def test_connector_source_metadata_records_pagination_and_watermark_without_secrets():
    api = ConnectorImportRequest(
        source_type="rest_api",
        record_type="products",
        api_url="https://supplier.example/catalog",
        api_page_param="page",
        api_page_size_param="limit",
        api_page_size=100,
        api_max_pages=5,
        api_retry_attempts=3,
        api_headers={"X-API-Key": "do-not-persist"},
    )
    parsed = routes.parse_source(
        b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]',
        "connector.json",
    )
    metadata = routes._source_metadata(api, parsed)
    assert metadata["pagination"]["mode"] == "page_number"
    assert metadata["pagination"]["max_pages"] == 5
    assert "do-not-persist" not in str(metadata)


@pytest.mark.anyio
async def test_connector_rate_limit_is_enforced_per_organization(monkeypatch):
    calls = {"count": 0, "closed": 0, "committed": 0, "deleted_old_buckets": 0}

    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class FakeSession:
        info = {}

        def get_bind(self):
            from types import SimpleNamespace
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def in_transaction(self):
            return False

        def execute(self, statement, params):
            if "INSERT INTO connector_rate_limits" in str(statement):
                calls["count"] += 1
                calls["window_start"] = params["window_start"]
                return FakeResult(calls["count"])
            calls["deleted_old_buckets"] += 1
            return FakeResult(None)

        def commit(self):
            calls["committed"] += 1

        def rollback(self):
            raise AssertionError("Unexpected rollback")

        def close(self):
            calls["closed"] += 1

    monkeypatch.setattr(routes, "SessionLocal", FakeSession)
    monkeypatch.setattr(settings, "connector_rate_limit_per_minute", 1)
    organization_id = uuid4()
    await routes._enforce_connector_rate_limit(organization_id, uuid4())
    with pytest.raises(Exception) as exc:
        await routes._enforce_connector_rate_limit(organization_id)
    assert getattr(exc.value, "status_code", None) == 429
    assert calls["count"] == 2
    assert calls["closed"] == 2
    assert calls["committed"] == 2
    assert calls["deleted_old_buckets"] == 2
    assert calls["window_start"].second == 0
    assert calls["window_start"].microsecond == 0


@pytest.mark.anyio
async def test_connector_rate_limit_fails_closed_when_postgres_is_unavailable(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    calls = {"rolled_back": False, "closed": False}

    class FakeSession:
        info = {}

        def get_bind(self):
            from types import SimpleNamespace
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def in_transaction(self):
            return False

        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("database unavailable")

        def rollback(self):
            calls["rolled_back"] = True

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(routes, "SessionLocal", FakeSession)
    with pytest.raises(Exception) as exc:
        await routes._enforce_connector_rate_limit(uuid4())
    assert getattr(exc.value, "status_code", None) == 503
    assert calls["rolled_back"] is True
    assert calls["closed"] is True


def test_sql_watermark_checkpoint_is_recorded_without_connection_secrets():
    payload = ConnectorImportRequest(
        source_type="sql_server",
        record_type="products",
        sql_server_url="mssql+pyodbc://reader:secret@sql.example/catalog?password=hidden",
        sql_schema="dbo",
        sql_table="Products",
        sql_columns=["modified_id", "sku"],
        sql_watermark_column="modified_id",
        sql_watermark_after="10",
    )
    parsed = routes.parse_source(
        b'[{"modified_id":11,"sku":"001"}]',
        "connector.json",
    )
    metadata = routes._source_metadata(payload, parsed)
    watermark = metadata["sql_server"]["watermark"]
    assert watermark == {
        "column": "modified_id",
        "after": "10",
        "next": "11",
        "strategy": "strictly_greater_than_unique_monotonic_key",
    }
    assert "secret" not in str(metadata) and "hidden" not in str(metadata)
