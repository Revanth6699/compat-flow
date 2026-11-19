import base64
from uuid import UUID, uuid4

import pytest

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
