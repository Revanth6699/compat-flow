import base64
from uuid import UUID, uuid4

import pytest
from types import SimpleNamespace
from fastapi import HTTPException

from app.api.connector_import_routes import (
    ConnectorImportRequest,
    _configuration_public,
    _resolve_connector_request,
    _source_metadata,
)
from app.core.config import settings
from app.services.connector_credentials import (
    CredentialVaultError,
    decrypt_credentials,
    encrypt_credentials,
    validate_connector_configuration,
)


KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ORG = UUID("11111111-1111-4111-8111-111111111111")
CONFIG = UUID("22222222-2222-4222-8222-222222222222")


def test_aes_gcm_credentials_round_trip_and_ciphertext_hides_secret():
    credentials = {"password": "supplier-secret"}
    encrypted = encrypt_credentials(
        credentials,
        encryption_key=KEY,
        organization_id=ORG,
        configuration_id=CONFIG,
        source_type="sftp",
    )
    assert "supplier-secret" not in encrypted
    assert decrypt_credentials(
        encrypted,
        encryption_key=KEY,
        organization_id=ORG,
        configuration_id=CONFIG,
        source_type="sftp",
    ) == credentials


def test_credentials_are_bound_to_organization_and_configuration():
    encrypted = encrypt_credentials(
        {"connection_url": "mssql+pyodbc://user:secret@db.example.com/catalog"},
        encryption_key=KEY,
        organization_id=ORG,
        configuration_id=CONFIG,
        source_type="sql_server",
    )
    with pytest.raises(CredentialVaultError, match="could not be decrypted"):
        decrypt_credentials(
            encrypted,
            encryption_key=KEY,
            organization_id=uuid4(),
            configuration_id=CONFIG,
            source_type="sql_server",
        )
    with pytest.raises(CredentialVaultError, match="could not be decrypted"):
        decrypt_credentials(
            encrypted,
            encryption_key=KEY,
            organization_id=ORG,
            configuration_id=uuid4(),
            source_type="sql_server",
        )


def test_tampered_ciphertext_is_rejected_without_secret_details():
    encrypted = encrypt_credentials(
        {"api_headers": {"Authorization": "Bearer hidden-token"}},
        encryption_key=KEY,
        organization_id=ORG,
        configuration_id=CONFIG,
        source_type="rest_api",
    )
    tampered = encrypted[:-2] + ("AA" if encrypted[-2:] != "AA" else "BB")
    with pytest.raises(CredentialVaultError, match="could not be decrypted"):
        decrypt_credentials(
            tampered,
            encryption_key=KEY,
            organization_id=ORG,
            configuration_id=CONFIG,
            source_type="rest_api",
        )


def test_missing_or_invalid_encryption_key_fails_closed():
    with pytest.raises(CredentialVaultError, match="not configured"):
        encrypt_credentials(
            {},
            encryption_key="",
            organization_id=ORG,
            configuration_id=CONFIG,
            source_type="rest_api",
        )
    with pytest.raises(CredentialVaultError, match="32 bytes"):
        encrypt_credentials(
            {},
            encryption_key=base64.urlsafe_b64encode(b"short").decode("ascii"),
            organization_id=ORG,
            configuration_id=CONFIG,
            source_type="rest_api",
        )


def test_credential_payload_size_is_bounded():
    with pytest.raises(CredentialVaultError, match="64 KiB"):
        encrypt_credentials(
            {"private_key": "x" * (64 * 1024)},
            encryption_key=KEY,
            organization_id=ORG,
            configuration_id=CONFIG,
            source_type="sftp",
        )


def test_rest_configuration_separates_headers_and_rejects_secret_query_parameters():
    settings, credentials, descriptor = validate_connector_configuration(
        "rest_api",
        {"api_url": "https://supplier.example.com/v1/products", "api_max_pages": 3,
         "api_page_param": "page", "api_page_size_param": "limit"},
        {"api_headers": {"Authorization": "Bearer hidden"}},
        allowed_hosts={"supplier.example.com"},
        sftp_known_hosts_configured=False,
    )
    assert settings["api_url"] == "https://supplier.example.com/v1/products"
    assert credentials["api_headers"]["Authorization"] == "Bearer hidden"
    assert descriptor == "https://supplier.example.com"

    with pytest.raises(CredentialVaultError, match="query parameters"):
        validate_connector_configuration(
            "rest_api",
            {"api_url": "https://supplier.example.com/v1?api_key=hidden"},
            {"api_headers": {}},
            allowed_hosts={"supplier.example.com"},
            sftp_known_hosts_configured=False,
        )


def test_rest_configuration_rejects_non_allowlisted_host_and_unknown_fields():
    with pytest.raises(CredentialVaultError, match="CONNECTOR_ALLOWED_HOSTS"):
        validate_connector_configuration(
            "rest_api",
            {"api_url": "https://other.example.com/v1"},
            {"api_headers": {}},
            allowed_hosts={"supplier.example.com"},
            sftp_known_hosts_configured=False,
        )
    with pytest.raises(CredentialVaultError, match="unsupported fields"):
        validate_connector_configuration(
            "rest_api",
            {"api_url": "https://supplier.example.com/v1", "password": "leak"},
            {"api_headers": {}},
            allowed_hosts={"supplier.example.com"},
            sftp_known_hosts_configured=False,
        )


def test_sftp_configuration_requires_exactly_one_secret_and_safe_remote_path():
    common = {
        "sftp_host": "sftp.example.com",
        "sftp_username": "readonly",
        "sftp_remote_path": "/feeds/catalog.csv",
    }
    settings, credentials, descriptor = validate_connector_configuration(
        "sftp",
        common,
        {"password": "secret"},
        allowed_hosts={"sftp.example.com"},
        sftp_known_hosts_configured=True,
    )
    assert settings["sftp_remote_path"] == "/feeds/catalog.csv"
    assert credentials["password"] == "secret"
    assert descriptor == "sftp://sftp.example.com/catalog.csv"

    with pytest.raises(CredentialVaultError, match="exactly one"):
        validate_connector_configuration(
            "sftp",
            common,
            {"password": "secret", "private_key": "-----BEGIN PRIVATE KEY-----"},
            allowed_hosts={"sftp.example.com"},
            sftp_known_hosts_configured=True,
        )
    with pytest.raises(CredentialVaultError, match="dot segments"):
        validate_connector_configuration(
            "sftp",
            {**common, "sftp_remote_path": "/feeds/../secrets.csv"},
            {"password": "secret"},
            allowed_hosts={"sftp.example.com"},
            sftp_known_hosts_configured=True,
        )


def test_sql_server_configuration_requires_driver_18_tls_and_read_only_intent():
    connection_url = (
        "mssql+pyodbc://readonly:secret@sql.example.com:1433/catalog"
        "?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes"
        "&TrustServerCertificate=no&ApplicationIntent=ReadOnly"
    )
    settings, credentials, descriptor = validate_connector_configuration(
        "sql_server",
        {
            "sql_schema": "dbo",
            "sql_table": "SupplierProducts",
            "sql_columns": ["ProductId", "UpdatedAt"],
            "sql_row_limit": 1000,
            "sql_watermark_column": "UpdatedAt",
            "sql_watermark_after": "2026-11-18T00:00:00",
        },
        {"connection_url": connection_url},
        allowed_hosts={"sql.example.com"},
        sftp_known_hosts_configured=False,
    )
    assert settings["sql_columns"] == ["ProductId", "UpdatedAt"]
    assert credentials["connection_url"] == connection_url
    assert descriptor == "sqlserver://sql.example.com/catalog/dbo.SupplierProducts"

    with pytest.raises(CredentialVaultError, match="certificate verification"):
        validate_connector_configuration(
            "sql_server",
            {"sql_schema": "dbo", "sql_table": "SupplierProducts", "sql_columns": ["ProductId"]},
            {"connection_url": connection_url.replace("TrustServerCertificate=no", "TrustServerCertificate=yes")},
            allowed_hosts={"sql.example.com"},
            sftp_known_hosts_configured=False,
        )


def test_configuration_public_view_never_exposes_ciphertext():
    item = SimpleNamespace(
        id=CONFIG,
        name="Supplier feed",
        source_type="rest_api",
        source_descriptor="https://supplier.example.com",
        source_settings={"api_url": "https://supplier.example.com/v1"},
        encrypted_credentials="ciphertext-must-not-leak",
        created_at=None,
    )
    public = _configuration_public(item)
    assert "encrypted_credentials" not in public
    assert "ciphertext-must-not-leak" not in str(public)


def test_saved_configuration_is_resolved_only_for_its_tenant(monkeypatch):
    encrypted = encrypt_credentials(
        {"api_headers": {"Authorization": "Bearer saved-secret"}},
        encryption_key=KEY,
        organization_id=ORG,
        configuration_id=CONFIG,
        source_type="rest_api",
    )
    item = SimpleNamespace(
        id=CONFIG,
        organization_id=ORG,
        source_type="rest_api",
        source_settings={"api_url": "https://supplier.example.com/v1"},
        encrypted_credentials=encrypted,
        encryption_key_version="v1",
        deleted_at=None,
    )
    monkeypatch.setattr(settings, "connector_credential_encryption_key", KEY)

    class FakeDB:
        def __init__(self, selected):
            self.selected = selected
            self.statement = ""

        def scalar(self, statement):
            self.statement = str(statement)
            if "role_permissions" in self.statement:
                return object()
            return self.selected

    payload = ConnectorImportRequest(
        source_type="rest_api",
        record_type="products",
        configuration_id=CONFIG,
    )
    db = FakeDB(item)
    resolved = _resolve_connector_request(payload, db, ORG, "admin")
    assert resolved.api_url == "https://supplier.example.com/v1"
    assert resolved.api_headers == {"Authorization": "Bearer saved-secret"}
    assert "connector_configurations.organization_id" in db.statement

    other_tenant_db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        _resolve_connector_request(payload, other_tenant_db, uuid4(), "admin")
    assert exc.value.status_code == 404
    assert "connector_configurations.organization_id" in other_tenant_db.statement


def test_saved_configuration_requires_catalog_write_permission():
    payload = ConnectorImportRequest(
        source_type="rest_api", record_type="products", configuration_id=CONFIG
    )

    class ReadOnlyDB:
        def scalar(self, statement):
            return None

    with pytest.raises(HTTPException) as exc:
        _resolve_connector_request(payload, ReadOnlyDB(), ORG, "viewer")
    assert exc.value.status_code == 403


def test_saved_configuration_cannot_be_mixed_with_inline_credentials():
    payload = ConnectorImportRequest(
        source_type="rest_api",
        record_type="products",
        configuration_id=CONFIG,
        api_url="https://attacker.example/override",
    )
    with pytest.raises(HTTPException) as exc:
        _resolve_connector_request(payload, SimpleNamespace(), ORG, "admin")
    assert exc.value.status_code == 422


def test_saved_configuration_decryption_fails_closed_for_wrong_key(monkeypatch):
    encrypted = encrypt_credentials(
        {"api_headers": {"X-API-Key": "saved-secret"}},
        encryption_key=KEY,
        organization_id=ORG,
        configuration_id=CONFIG,
        source_type="rest_api",
    )
    item = SimpleNamespace(
        id=CONFIG,
        organization_id=ORG,
        source_type="rest_api",
        source_settings={"api_url": "https://supplier.example.com/v1"},
        encrypted_credentials=encrypted,
        encryption_key_version="v1",
        deleted_at=None,
    )
    monkeypatch.setattr(
        settings,
        "connector_credential_encryption_key",
        base64.urlsafe_b64encode(b"z" * 32).decode("ascii"),
    )

    class FakeDB:
        def scalar(self, statement):
            return item

    payload = ConnectorImportRequest(
        source_type="rest_api", record_type="products", configuration_id=CONFIG
    )
    with pytest.raises(HTTPException) as exc:
        _resolve_connector_request(payload, FakeDB(), ORG, "admin")
    assert exc.value.status_code == 503
    assert "saved-secret" not in str(exc.value.detail)


def test_signed_url_query_credentials_are_rejected():
    with pytest.raises(CredentialVaultError, match="query parameters"):
        validate_connector_configuration(
            "rest_api",
            {"api_url": "https://supplier.example.com/v1?sig=signed-token"},
            {"api_headers": {}},
            allowed_hosts={"supplier.example.com"},
            sftp_known_hosts_configured=False,
        )


def test_import_history_metadata_records_saved_configuration_id_not_credentials():
    payload = ConnectorImportRequest(
        source_type="rest_api",
        record_type="products",
        configuration_id=CONFIG,
        api_headers={"Authorization": "Bearer never-store-this"},
    )
    parsed = SimpleNamespace(metadata={"format": "json", "records": 1})
    metadata = _source_metadata(payload, parsed)
    assert metadata["connector_configuration_id"] == str(CONFIG)
    assert "never-store-this" not in str(metadata)
