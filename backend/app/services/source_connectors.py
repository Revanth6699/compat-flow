"""Secure, read-only source connector primitives for scheduled ingestion.

Secrets and connection URLs must be injected by the deployment secret manager.
This module deliberately does not expose arbitrary write SQL or persist credentials.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import unquote_plus
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import make_url


class SourceConnectorError(RuntimeError):
    pass


def _validate_https_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment):
        raise SourceConnectorError("Connector URL must be an HTTPS URL without embedded credentials.")
    host = parsed.hostname.casefold().rstrip(".")
    if host not in {item.casefold().rstrip(".") for item in allowed_hosts}:
        raise SourceConnectorError("Connector host is not in the configured allowlist.")
    try:
        resolved = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError:
        raise SourceConnectorError("Connector host could not be resolved.") from None
    for value in resolved:
        address = ipaddress.ip_address(value)
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_unspecified):
            raise SourceConnectorError("Private and local network targets are not allowed.")


async def fetch_api_records(url: str, *, allowed_hosts: set[str],
                            headers: dict[str, str] | None = None,
                            records_key: str | None = None, timeout_seconds: float = 20,
                            max_bytes: int = 10 * 1024 * 1024) -> list[dict[str, Any]]:
    """Fetch one bounded JSON API page. Pagination must be explicitly configured by caller."""
    _validate_https_url(url, allowed_hosts)
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise SourceConnectorError("API response exceeds the configured size limit.")
                chunks = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise SourceConnectorError("API response exceeds the configured size limit.")
                    chunks.append(chunk)
        import json
        payload = json.loads(b"".join(chunks))
    except SourceConnectorError:
        raise
    except (httpx.HTTPError, ValueError, TypeError):
        raise SourceConnectorError("API request failed or returned invalid JSON.") from None
    if records_key:
        for part in records_key.split("."):
            if not isinstance(payload, dict) or part not in payload:
                raise SourceConnectorError("Configured API records path does not exist.")
            payload = payload[part]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise SourceConnectorError("API response must contain an object or an array of objects.")
    return payload


def fetch_sftp_file(*, host: str, port: int, username: str, password: str | None = None,
                    private_key: str | None = None, remote_path: str,
                    known_hosts_path: str, max_bytes: int = 10 * 1024 * 1024) -> bytes:
    """Download a single file using verified SSH host keys; unknown hosts are rejected."""
    if not known_hosts_path or not remote_path.startswith("/") or "\x00" in remote_path:
        raise SourceConnectorError("An absolute remote path and known-hosts file are required.")
    if not password and not private_key:
        raise SourceConnectorError("SFTP authentication credentials are required.")
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.load_host_keys(known_hosts_path)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(hostname=host, port=port, username=username, password=password,
                       key_filename=private_key, look_for_keys=False, allow_agent=False,
                       timeout=15, banner_timeout=15, auth_timeout=15)
        try:
            with client.open_sftp() as sftp:
                with sftp.open(remote_path, "rb") as remote:
                    content = remote.read(max_bytes + 1)
                    if len(content) > max_bytes:
                        raise SourceConnectorError("SFTP file exceeds the configured size limit.")
                    return content
        finally:
            client.close()
    except SourceConnectorError:
        raise
    except Exception:
        raise SourceConnectorError("SFTP connection or file retrieval failed.") from None


def fetch_sql_server_rows(connection_url: str, *, schema: str, table: str,
                          columns: list[str], limit: int = 10_000) -> list[dict[str, Any]]:
    """Read a bounded projection from SQL Server; arbitrary SQL is intentionally unsupported."""
    if not connection_url.startswith("mssql+pyodbc://"):
        raise SourceConnectorError("SQL Server requires a mssql+pyodbc connection URL and configured ODBC driver.")
    try:
        parsed_url = make_url(connection_url)
    except Exception:
        raise SourceConnectorError("SQL Server connection URL is invalid.") from None
    query = parsed_url.query
    odbc_connect = unquote_plus(str(query.get("odbc_connect", "")))
    connection_options = ";".join(
        [f"{key}={value}" for key, value in query.items()] + [odbc_connect]
    )
    if "ODBC Driver 18" not in connection_options:
        raise SourceConnectorError("SQL Server must use Microsoft ODBC Driver 18.")
    if not re.search(r"Encrypt\s*=\s*(yes|true)", connection_options, re.IGNORECASE):
        raise SourceConnectorError("SQL Server connections must enable encryption.")
    if not re.search(r"TrustServerCertificate\s*=\s*(no|false)", connection_options, re.IGNORECASE):
        raise SourceConnectorError("SQL Server certificate verification must remain enabled.")
    identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    if not identifier.fullmatch(schema) or not identifier.fullmatch(table):
        raise SourceConnectorError("Invalid SQL Server schema or table identifier.")
    if not columns or len(columns) > 200 or any(not identifier.fullmatch(col) for col in columns):
        raise SourceConnectorError("Provide between 1 and 200 valid column identifiers.")
    if not 1 <= limit <= 10_000:
        raise SourceConnectorError("SQL Server row limit must be between 1 and 10,000.")
    try:
        engine = create_engine(connection_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
        try:
            with engine.connect() as connection:
                source_table = Table(table, MetaData(), schema=schema, autoload_with=connection)
                selected_columns = [source_table.c[column] for column in columns]
                statement = select(*selected_columns).limit(limit)
                rows = connection.execute(statement).mappings().all()
                return [dict(row) for row in rows]
        finally:
            engine.dispose()
    except Exception:
        raise SourceConnectorError("SQL Server read failed; verify the read-only login, ODBC driver, and source schema.") from None
