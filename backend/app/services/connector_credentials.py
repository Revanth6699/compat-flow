"""Tenant-scoped connector configuration validation and authenticated encryption."""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
from typing import Any
from urllib.parse import parse_qsl, unquote_plus, urlsplit
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.engine import make_url


class CredentialVaultError(ValueError):
    """Safe connector configuration or credential-vault failure."""


_KEY_VERSION = "v1"
_NONCE_BYTES = 12
_MAX_CREDENTIAL_BYTES = 64 * 1024
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_QUERY_SECRET_NAMES = {
    "api_key", "apikey", "access_token", "token", "password",
    "client_secret", "secret", "authorization", "signature", "auth",
    "credential", "x_api_key", "key", "accesskey", "secretkey", "auth_token",
    "refresh_token", "client_assertion", "awsaccesskeyid", "x_amz_credential",
    "x_amz_signature", "x_goog_signature", "sig", "se", "sp", "sv", "sr", "st",
    "code", "jwt", "subscription_key", "ocp_apim_subscription_key",
}


def _decode_key(encoded_key: str | None) -> bytes:
    if not encoded_key:
        raise CredentialVaultError(
            "Connector credential encryption is not configured."
        )
    try:
        key = base64.b64decode(
            encoded_key.encode("ascii"), altchars=b"-_", validate=True
        )
    except (UnicodeEncodeError, binascii.Error, ValueError):
        raise CredentialVaultError(
            "Connector credential encryption key must be URL-safe base64."
        ) from None
    if len(key) != 32:
        raise CredentialVaultError(
            "Connector credential encryption key must decode to exactly 32 bytes."
        )
    return key


def _aad(
    organization_id: UUID,
    configuration_id: UUID,
    source_type: str,
    key_version: str = _KEY_VERSION,
) -> bytes:
    return (
        f"compatflow:connector:{key_version}:{organization_id}:"
        f"{configuration_id}:{source_type}"
    ).encode("utf-8")


def encrypt_credentials(
    credentials: dict[str, Any],
    *,
    encryption_key: str | None,
    organization_id: UUID,
    configuration_id: UUID,
    source_type: str,
) -> str:
    """Encrypt JSON credentials with AES-256-GCM and tenant/configuration AAD."""
    if not isinstance(credentials, dict):
        raise CredentialVaultError("Connector credentials must be an object.")
    try:
        plaintext = json.dumps(
            credentials, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise CredentialVaultError("Connector credentials are not serializable.") from None
    if len(plaintext) > _MAX_CREDENTIAL_BYTES:
        raise CredentialVaultError("Connector credentials exceed the 64 KiB limit.")
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_decode_key(encryption_key)).encrypt(
        nonce,
        plaintext,
        _aad(organization_id, configuration_id, source_type),
    )
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_credentials(
    encrypted_value: str,
    *,
    encryption_key: str | None,
    organization_id: UUID,
    configuration_id: UUID,
    source_type: str,
    key_version: str = _KEY_VERSION,
) -> dict[str, Any]:
    """Decrypt only for the owning tenant and exact connector configuration."""
    if key_version != _KEY_VERSION:
        raise CredentialVaultError(
            "Connector credential encryption version is not supported."
        )
    try:
        packed = base64.b64decode(
            encrypted_value.encode("ascii"), altchars=b"-_", validate=True
        )
        if len(packed) <= _NONCE_BYTES + 16:
            raise ValueError("ciphertext too short")
        plaintext = AESGCM(_decode_key(encryption_key)).decrypt(
            packed[:_NONCE_BYTES],
            packed[_NONCE_BYTES:],
            _aad(organization_id, configuration_id, source_type, key_version),
        )
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("credential payload is not an object")
        return decoded
    except CredentialVaultError:
        raise
    except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError, ValueError, binascii.Error):
        raise CredentialVaultError(
            "Stored connector credentials could not be decrypted."
        ) from None


def _require_keys(
    value: dict[str, Any], allowed: set[str], label: str
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise CredentialVaultError(
            f"{label} contains unsupported fields: {', '.join(sorted(unknown))}."
        )


def _allowed_host(host: str | None, allowed_hosts: set[str]) -> str:
    normalized = (host or "").casefold().rstrip(".")
    allowed = {item.casefold().rstrip(".") for item in allowed_hosts}
    if not normalized or not allowed or normalized not in allowed:
        raise CredentialVaultError(
            "Connector host must exactly match CONNECTOR_ALLOWED_HOSTS."
        )
    return normalized


def _bounded_int(
    settings: dict[str, Any], name: str, default: int, minimum: int, maximum: int
) -> int:
    value = settings.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise CredentialVaultError(
            f"{name} must be an integer between {minimum} and {maximum}."
        )
    return value


def validate_connector_configuration(
    source_type: str,
    source_settings: dict[str, Any],
    credentials: dict[str, Any],
    *,
    allowed_hosts: set[str],
    sftp_known_hosts_configured: bool,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Validate and separate non-secret source settings from encrypted credentials."""
    if not isinstance(source_settings, dict) or not isinstance(credentials, dict):
        raise CredentialVaultError(
            "Connector settings and credentials must be JSON objects."
        )

    settings = dict(source_settings)
    secrets = dict(credentials)

    if source_type == "rest_api":
        _require_keys(
            settings,
            {
                "api_url", "api_records_path", "api_page_param",
                "api_page_size_param", "api_page_size", "api_start_page",
                "api_max_pages", "api_retry_attempts",
            },
            "REST API settings",
        )
        _require_keys(secrets, {"api_headers"}, "REST API credentials")
        raw_url = settings.get("api_url")
        try:
            parsed = urlsplit(raw_url if isinstance(raw_url, str) else "")
            port = parsed.port
        except ValueError:
            raise CredentialVaultError("REST API URL is invalid.") from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise CredentialVaultError(
                "REST API configuration requires HTTPS without embedded credentials or fragments."
            )
        host = _allowed_host(parsed.hostname, allowed_hosts)
        if any(
            name.casefold().replace("-", "_") in _QUERY_SECRET_NAMES
            for name, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise CredentialVaultError(
                "REST API credentials cannot be stored in URL query parameters."
            )
        records_path = settings.get("api_records_path")
        if records_path is not None and (
            not isinstance(records_path, str)
            or not records_path
            or len(records_path) > 512
            or any(not part for part in records_path.split("."))
        ):
            raise CredentialVaultError("REST API records path is invalid.")
        page_param = settings.get("api_page_param")
        size_param = settings.get("api_page_size_param")
        if bool(page_param) != bool(size_param):
            raise CredentialVaultError(
                "REST API pagination requires both page and page-size parameter names."
            )
        if page_param and (
            not isinstance(page_param, str)
            or not isinstance(size_param, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", page_param)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", size_param)
            or page_param == size_param
        ):
            raise CredentialVaultError("REST API pagination parameter names are invalid.")
        _bounded_int(settings, "api_page_size", 500, 1, 1000)
        _bounded_int(settings, "api_start_page", 1, 0, 1_000_000)
        _bounded_int(settings, "api_max_pages", 1, 1, 20)
        _bounded_int(settings, "api_retry_attempts", 2, 0, 5)
        headers = secrets.get("api_headers", {})
        if not isinstance(headers, dict) or len(headers) > 10:
            raise CredentialVaultError("REST API headers must be a bounded object.")
        allowed_headers = {"authorization", "x-api-key", "accept"}
        seen: set[str] = set()
        for name, value in headers.items():
            lowered = name.casefold() if isinstance(name, str) else ""
            if (
                lowered not in allowed_headers
                or lowered in seen
                or not isinstance(value, str)
                or len(name) > 64
                or len(value) > 4096
                or "\r" in value
                or "\n" in value
            ):
                raise CredentialVaultError(
                    "REST API headers must use bounded Authorization, X-API-Key, or Accept values."
                )
            seen.add(lowered)
        descriptor = f"https://{host}{f':{port}' if port else ''}"
        return settings, secrets, descriptor

    if source_type == "sftp":
        _require_keys(
            settings,
            {"sftp_host", "sftp_port", "sftp_username", "sftp_remote_path", "sftp_filename"},
            "SFTP settings",
        )
        _require_keys(secrets, {"password", "private_key"}, "SFTP credentials")
        host = _allowed_host(settings.get("sftp_host"), allowed_hosts)
        if not sftp_known_hosts_configured:
            raise CredentialVaultError("SFTP known-hosts configuration is not available.")
        username = settings.get("sftp_username")
        remote_path = settings.get("sftp_remote_path")
        if not isinstance(username, str) or not username.strip() or len(username) > 128:
            raise CredentialVaultError("SFTP username is required and must be bounded.")
        if (
            not isinstance(remote_path, str)
            or not remote_path.startswith("/")
            or "\x00" in remote_path
            or len(remote_path) > 1024
            or any(part in {".", ".."} for part in remote_path.split("/"))
        ):
            raise CredentialVaultError(
                "SFTP remote path must be absolute and contain no dot segments."
            )
        _bounded_int(settings, "sftp_port", 22, 1, 65535)
        filename = settings.get("sftp_filename")
        if filename is not None and (
            not isinstance(filename, str) or not filename or len(filename) > 255
        ):
            raise CredentialVaultError("SFTP filename is invalid.")
        password = secrets.get("password")
        private_key = secrets.get("private_key")
        if bool(password) == bool(private_key):
            raise CredentialVaultError(
                "Provide exactly one SFTP password or private key."
            )
        if password and (
            not isinstance(password, str) or len(password) > 4096
        ):
            raise CredentialVaultError("SFTP password exceeds the supported limit.")
        if private_key and (
            not isinstance(private_key, str)
            or len(private_key) > 64 * 1024
            or not private_key.strip().splitlines()
            or not private_key.strip().splitlines()[0].startswith("-----BEGIN ")
            or "PRIVATE KEY-----" not in private_key.strip().splitlines()[0]
        ):
            raise CredentialVaultError(
                "SFTP private key must be bounded, unencrypted PEM/OpenSSH key content."
            )
        filename = filename or remote_path.rsplit("/", 1)[-1]
        descriptor = f"sftp://{host}/{filename[:200]}"
        return settings, secrets, descriptor

    if source_type == "sql_server":
        _require_keys(
            settings,
            {
                "sql_schema", "sql_table", "sql_columns", "sql_row_limit",
                "sql_watermark_column", "sql_watermark_after",
            },
            "SQL Server settings",
        )
        _require_keys(secrets, {"connection_url"}, "SQL Server credentials")
        connection_url = secrets.get("connection_url")
        if not isinstance(connection_url, str) or len(connection_url) > 8192:
            raise CredentialVaultError("SQL Server connection URL is invalid.")
        try:
            parsed_url = make_url(connection_url)
        except Exception:
            raise CredentialVaultError("SQL Server connection URL is invalid.") from None
        if (
            parsed_url.drivername != "mssql+pyodbc"
            or not parsed_url.username
            or not parsed_url.password
            or not parsed_url.database
        ):
            raise CredentialVaultError(
                "SQL Server requires a SQL-authenticated mssql+pyodbc URL with a database."
            )
        host = _allowed_host(parsed_url.host, allowed_hosts)
        query = parsed_url.query
        odbc_connect = unquote_plus(str(query.get("odbc_connect", "")))
        connection_options = " ".join(
            [f"{key}={value}" for key, value in query.items()] + [odbc_connect]
        )
        if "ODBC Driver 18" not in connection_options:
            raise CredentialVaultError("SQL Server must use Microsoft ODBC Driver 18.")
        if not re.search(r"Encrypt\s*=\s*(yes|true)", connection_options, re.IGNORECASE):
            raise CredentialVaultError("SQL Server encryption must be enabled.")
        if not re.search(
            r"TrustServerCertificate\s*=\s*(no|false)",
            connection_options,
            re.IGNORECASE,
        ):
            raise CredentialVaultError("SQL Server certificate verification must be enabled.")
        if not re.search(
            r"ApplicationIntent\s*=\s*ReadOnly", connection_options, re.IGNORECASE
        ):
            raise CredentialVaultError("SQL Server ApplicationIntent must be ReadOnly.")
        schema = settings.get("sql_schema")
        table = settings.get("sql_table")
        columns = settings.get("sql_columns")
        if (
            not isinstance(schema, str)
            or not _IDENTIFIER.fullmatch(schema)
            or not isinstance(table, str)
            or not _IDENTIFIER.fullmatch(table)
            or not isinstance(columns, list)
            or not 1 <= len(columns) <= 200
            or any(not isinstance(column, str) or not _IDENTIFIER.fullmatch(column) for column in columns)
            or len(set(columns)) != len(columns)
        ):
            raise CredentialVaultError("SQL Server schema, table, or projection is invalid.")
        _bounded_int(settings, "sql_row_limit", 10_000, 1, 10_000)
        watermark_column = settings.get("sql_watermark_column")
        watermark_after = settings.get("sql_watermark_after")
        if bool(watermark_column) != bool(watermark_after):
            raise CredentialVaultError(
                "SQL Server watermark column and last committed value must be configured together."
            )
        if watermark_column and (
            not isinstance(watermark_column, str)
            or not _IDENTIFIER.fullmatch(watermark_column)
            or watermark_column not in columns
            or not isinstance(watermark_after, str)
            or len(watermark_after) > 128
        ):
            raise CredentialVaultError("SQL Server watermark configuration is invalid.")
        descriptor = (
            f"sqlserver://{host}/{parsed_url.database}/{schema}.{table}"
        )[:512]
        return settings, secrets, descriptor

    raise CredentialVaultError("Connector source type is not supported.")
