import base64
import threading

import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace
from uuid import uuid4

from app.main import app
from app.core.config import settings
from app.core.auth import AuthenticatedUser, SupabaseIdentity, get_current_user
from app.core.database import get_db
from app.api import connector_import_routes as routes
from app.api import routes as file_import_routes
from app.api.connector_import_routes import ConnectorImportRequest, _prepare, _require_allowed_host
from app.services.connector_credentials import decrypt_credentials, encrypt_credentials

client = TestClient(app)


async def _async_noop():
    return None


@pytest.mark.anyio
async def test_blocking_sftp_and_sql_reads_run_outside_the_event_loop(monkeypatch):
    event_loop_thread = threading.get_ident()
    calls = {}
    monkeypatch.setattr(
        settings,
        "connector_allowed_hosts",
        "sftp.supplier.example,sql.example",
    )
    monkeypatch.setattr(settings, "sftp_known_hosts_path", "/known_hosts")

    def fake_sftp(**kwargs):
        calls["sftp_thread"] = threading.get_ident()
        return b"SKU,Name\n001,Widget"

    def fake_sql(url, **kwargs):
        calls["sql_thread"] = threading.get_ident()
        return [{"sku": "001"}]

    monkeypatch.setattr(routes, "fetch_sftp_file", fake_sftp)
    sftp_payload = ConnectorImportRequest(
        source_type="sftp",
        record_type="products",
        sftp_host="sftp.supplier.example",
        sftp_username="reader",
        sftp_password="request-scoped-secret",
        sftp_remote_path="/exports/catalog.csv",
    )
    sftp_content, sftp_filename = await routes._load_source(sftp_payload)
    assert sftp_content.startswith(b"SKU,Name")
    assert sftp_filename == "catalog.csv"
    assert calls["sftp_thread"] != event_loop_thread

    monkeypatch.setattr(routes, "fetch_sql_server_rows", fake_sql)
    sql_payload = ConnectorImportRequest(
        source_type="sql_server",
        record_type="products",
        sql_server_url="mssql+pyodbc://reader:request-scoped-secret@sql.example/catalog",
        sql_schema="dbo",
        sql_table="Products",
        sql_columns=["sku"],
    )
    sql_content, sql_filename = await routes._load_source(sql_payload)
    assert sql_filename == "connector.json"
    assert b'"sku": "001"' in sql_content
    assert calls["sql_thread"] != event_loop_thread


def test_connector_routes_require_authentication():
    payload = {
        "source_type": "rest_api",
        "record_type": "products",
        "api_url": "https://supplier.example/catalog",
    }
    assert client.post("/api/v1/catalog/import/connectors/preview", json=payload).status_code == 401
    assert client.post("/api/v1/catalog/import/connectors/commit", json=payload).status_code == 401
    assert client.get("/api/v1/catalog/import/history").status_code == 401
    config_payload = {
        "name": "Supplier API",
        "source_type": "rest_api",
        "source_settings": {"api_url": "https://supplier.example/catalog"},
        "credentials": {"api_headers": {"X-API-Key": "must-not-be-returned"}},
    }
    assert client.post(
        "/api/v1/catalog/import/connectors/configurations", json=config_payload
    ).status_code == 401
    assert client.get(
        "/api/v1/catalog/import/connectors/configurations"
    ).status_code == 401
    config_id = "00000000-0000-0000-0000-000000000001"
    assert client.delete(
        f"/api/v1/catalog/import/connectors/configurations/{config_id}"
    ).status_code == 401
    assert client.post(
        f"/api/v1/catalog/import/connectors/configurations/{config_id}/rotate-credentials"
    ).status_code == 401
    assert client.get(
        f"/api/v1/catalog/import/connectors/configurations/{config_id}/audit"
    ).status_code == 401


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
    calls = {"count": 0, "closed": False}

    class FakeRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def eval(self, script, key_count, key, expiry):
            calls["count"] += 1
            return calls["count"]

        async def aclose(self):
            calls["closed"] = True

    monkeypatch.setattr(routes, "Redis", FakeRedis)
    monkeypatch.setattr(settings, "connector_rate_limit_per_minute", 1)
    organization_id = uuid4()
    await routes._enforce_connector_rate_limit(organization_id)
    with pytest.raises(Exception) as exc:
        await routes._enforce_connector_rate_limit(organization_id)
    assert getattr(exc.value, "status_code", None) == 429
    assert calls["count"] == 2
    assert calls["closed"] is True


@pytest.mark.anyio
async def test_connector_rate_limit_fails_closed_when_redis_is_unavailable(monkeypatch):
    class FakeRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def eval(self, *args):
            from redis.exceptions import RedisError
            raise RedisError("connection failed")

        async def aclose(self):
            pass

    monkeypatch.setattr(routes, "Redis", FakeRedis)
    with pytest.raises(Exception) as exc:
        await routes._enforce_connector_rate_limit(uuid4())
    assert getattr(exc.value, "status_code", None) == 503



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


def test_connector_preview_returns_opt_in_ai_classification_and_mapping_without_credentials(monkeypatch):
    _, _, _ = install_connector_auth(monkeypatch)
    captured = {}

    async def fake_load_source(payload):
        captured["connector_secret"] = payload.api_headers.get("Authorization")
        return (
            b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]',
            "supplier.json",
        )

    async def fake_suggest_field_mappings(**kwargs):
        captured["ai_input"] = kwargs
        return SimpleNamespace(
            status="suggestions_ready",
            message="Review suggestions before applying.",
            classification=SimpleNamespace(
                record_type="products",
                confidence=0.9,
                rationale="Product SKU and descriptive fields are present.",
                evidence=["sku", "name"],
            ),
            suggestions=[
                SimpleNamespace(
                    source_header="sku",
                    candidate_field="sku",
                    confidence=0.99,
                    rationale="Header matches the catalog SKU field.",
                    evidence=["sku", "001"],
                )
            ],
        )

    monkeypatch.setattr(routes, "_load_source", fake_load_source)
    monkeypatch.setattr(routes, "_enforce_connector_rate_limit", lambda organization_id: _async_noop())
    monkeypatch.setattr(routes, "suggest_field_mappings", fake_suggest_field_mappings)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/connectors/preview",
            json={
                "source_type": "rest_api",
                "record_type": "products",
                "api_url": "https://supplier.example/catalog",
                "api_headers": {"Authorization": "Bearer connector-secret"},
                "ai_opt_in": True,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["ai"]["status"] == "suggestions_ready"
        assert data["ai"]["source_data_sent"] is True
        assert data["ai"]["confidence_calibration"] == "model_reported_uncalibrated"
        assert data["ai"]["classification"]["record_type"] == "products"
        assert data["ai"]["classification"]["requires_confirmation"] is True
        assert data["ai"]["suggestions"][0]["candidate_field"] == "sku"
        assert data["ai"]["suggestions"][0]["requires_confirmation"] is True
        assert captured["connector_secret"] == "Bearer connector-secret"
        assert set(captured["ai_input"]["headers"]) == {"sku", "name", "manufacturer", "part_number", "category"}
        assert captured["ai_input"]["sample_records"][0]["sku"] == "001"
        assert "connector-secret" not in str(captured["ai_input"])
    finally:
        clear_connector_auth()


def test_connector_preview_does_not_send_ai_evidence_without_opt_in(monkeypatch):
    install_connector_auth(monkeypatch)
    captured = {"called": False}

    async def fake_load_source(payload):
        return (
            b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]',
            "supplier.json",
        )

    async def fake_suggest_field_mappings(**kwargs):
        captured["called"] = True
        assert kwargs["user_opted_in"] is False
        return SimpleNamespace(
            status="consent_required",
            message="AI suggestions are opt-in; no source data was sent.",
            classification=None,
            suggestions=[],
        )

    monkeypatch.setattr(routes, "_load_source", fake_load_source)
    monkeypatch.setattr(routes, "_enforce_connector_rate_limit", lambda organization_id: _async_noop())
    monkeypatch.setattr(routes, "suggest_field_mappings", fake_suggest_field_mappings)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/connectors/preview",
            json={
                "source_type": "rest_api",
                "record_type": "products",
                "api_url": "https://supplier.example/catalog",
                "ai_opt_in": False,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["ai"]["status"] == "consent_required"
        assert data["ai"]["source_data_sent"] is False
        assert data["ai"]["classification"] is None
        assert captured["called"] is True
    finally:
        clear_connector_auth()


def test_file_ai_endpoint_returns_record_classification_and_mapping(monkeypatch):
    install_connector_auth(monkeypatch)
    captured = {}

    async def fake_suggest_field_mappings(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            status="suggestions_ready",
            message="Review the classification and mappings.",
            classification=SimpleNamespace(
                record_type="product_identifiers",
                confidence=0.88,
                rationale="The sample contains a typed identifier value.",
                evidence=["identifier_type", "value"],
            ),
            suggestions=[
                SimpleNamespace(
                    source_header="value",
                    candidate_field="value",
                    confidence=0.97,
                    rationale="The source header is an identifier value.",
                    evidence=["value", "00012345678905"],
                )
            ],
        )

    monkeypatch.setattr(file_import_routes, "suggest_field_mappings", fake_suggest_field_mappings)
    try:
        response = TestClient(app).post(
            "/api/v1/catalog/import/suggest-mappings",
            data={"record_type": "product_identifiers", "ai_opt_in": "true"},
            files={
                "file": (
                    "identifiers.json",
                    b'[{"identifier_type":"gtin","value":"00012345678905","product_id":"00000000-0000-0000-0000-000000000001"}]',
                    "application/json",
                )
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["classification"]["record_type"] == "product_identifiers"
        assert data["classification"]["requires_confirmation"] is True
        assert data["suggestions"][0]["candidate_field"] == "value"
        assert data["suggestions"][0]["requires_confirmation"] is True
        assert data["confidence_calibration"] == "model_reported_uncalibrated"
        assert data["source_data_sent"] is True
        assert set(captured["headers"]) == {"identifier_type", "value", "product_id"}
        assert captured["sample_records"][0]["value"] == "00012345678905"
        assert captured["user_opted_in"] is True
    finally:
        clear_connector_auth()



def test_saved_configuration_rotation_is_tenant_scoped_and_audited(monkeypatch):
    organization_id, current, _ = install_connector_auth(monkeypatch)
    current.profile.role = "admin"
    old_key = base64.urlsafe_b64encode(b"o" * 32).decode("ascii")
    new_key = base64.urlsafe_b64encode(b"n" * 32).decode("ascii")
    configuration_id = uuid4()
    credentials = {"api_headers": {"Authorization": "Bearer rotation-secret"}}
    encrypted = encrypt_credentials(
        credentials,
        encryption_key=old_key,
        organization_id=organization_id,
        configuration_id=configuration_id,
        source_type="rest_api",
        key_version="v1",
    )
    item = SimpleNamespace(
        id=configuration_id,
        organization_id=organization_id,
        source_type="rest_api",
        source_descriptor="https://supplier.example",
        encryption_key_version="v1",
        encrypted_credentials=encrypted,
        deleted_at=None,
    )
    monkeypatch.setattr(settings, "connector_credential_encryption_key", new_key)
    monkeypatch.setattr(settings, "connector_credential_encryption_key_version", "v2")
    monkeypatch.setattr(
        settings,
        "connector_credential_encryption_previous_keys",
        '{"v1":"' + old_key + '"}',
    )

    class RotationDB:
        def __init__(self):
            self.subscription = SimpleNamespace(status="active", plan_code="growth", current_period_end=None)
            self.plan = SimpleNamespace(code="growth", is_active=True, entitlements={"supplier_catalogs": True})
            self.events = []
            self.committed = False

        def scalar(self, statement):
            query = str(statement)
            if "role_permissions" in query:
                return object()
            if "connector_configurations" in query:
                return item
            if "subscriptions" in query:
                return self.subscription
            return object()

        def get(self, model, key):
            return self.plan

        def add(self, event):
            self.events.append(event)

        def commit(self):
            self.committed = True

    db = RotationDB()
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).post(
            f"/api/v1/catalog/import/connectors/configurations/{configuration_id}/rotate-credentials"
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"rotated": True, "key_version": "v2"}
        assert item.encryption_key_version == "v2"
        assert db.committed is True
        assert len(db.events) == 1
        assert db.events[0].action == "credentials_rotated"
        assert db.events[0].key_version_from == "v1"
        assert db.events[0].key_version_to == "v2"
        assert decrypt_credentials(
            item.encrypted_credentials,
            encryption_key=new_key,
            organization_id=organization_id,
            configuration_id=configuration_id,
            source_type="rest_api",
            key_version="v2",
        ) == credentials
        assert "rotation-secret" not in str(db.events[0].__dict__)
    finally:
        clear_connector_auth()


def test_saved_configuration_audit_lookup_does_not_cross_tenant(monkeypatch):
    _, current, _ = install_connector_auth(monkeypatch)
    current.profile.role = "admin"

    class TenantDB:
        subscription = SimpleNamespace(status="active", plan_code="growth", current_period_end=None)
        plan = SimpleNamespace(code="growth", is_active=True, entitlements={"supplier_catalogs": True})

        def scalar(self, statement):
            query = str(statement)
            if "role_permissions" in query:
                return object()
            if "subscriptions" in query:
                return self.subscription
            if "connector_configurations" in query:
                return None
            return object()

        def get(self, model, key):
            return self.plan

    app.dependency_overrides[get_db] = lambda: TenantDB()
    try:
        response = TestClient(app).get(
            f"/api/v1/catalog/import/connectors/configurations/{uuid4()}/audit"
        )
        assert response.status_code == 404
    finally:
        clear_connector_auth()



def test_member_cannot_manage_saved_connector_configurations(monkeypatch):
    install_connector_auth(monkeypatch)
    configuration_id = uuid4()
    config_payload = {
        "name": "Supplier API",
        "source_type": "rest_api",
        "source_settings": {"api_url": "https://supplier.example/catalog"},
        "credentials": {"api_headers": {"X-API-Key": "secret"}},
    }
    try:
        create = TestClient(app).post(
            "/api/v1/catalog/import/connectors/configurations",
            json=config_payload,
        )
        delete = TestClient(app).delete(
            f"/api/v1/catalog/import/connectors/configurations/{configuration_id}"
        )
        rotate = TestClient(app).post(
            f"/api/v1/catalog/import/connectors/configurations/{configuration_id}/rotate-credentials"
        )
        audit = TestClient(app).get(
            f"/api/v1/catalog/import/connectors/configurations/{configuration_id}/audit"
        )
        assert [create.status_code, delete.status_code, rotate.status_code, audit.status_code] == [
            403, 403, 403, 403
        ]
    finally:
        clear_connector_auth()
