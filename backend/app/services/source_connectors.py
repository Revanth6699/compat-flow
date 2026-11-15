"""Secure, bounded source connector primitives for catalog ingestion.

Connector credentials are request-scoped. This module never persists or logs them.
REST pagination is explicit page-number pagination; supplier-specific cursor
protocols require a dedicated adapter rather than guessing response semantics.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlencode, unquote_plus, urlsplit, urlunsplit

import httpx
import pyodbc
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.engine import make_url


class SourceConnectorError(RuntimeError):
    """Safe, non-secret-bearing connector failure."""


def _validate_https_url(url: str, allowed_hosts: set[str]) -> None:
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise SourceConnectorError("Connector URL is invalid.") from None
    try:
        port = parsed.port or 443
    except ValueError:
        raise SourceConnectorError("Connector URL contains an invalid port.") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise SourceConnectorError(
            "Connector URL must be an HTTPS URL without embedded credentials."
        )
    host = parsed.hostname.casefold().rstrip(".")
    if host not in {item.casefold().rstrip(".") for item in allowed_hosts}:
        raise SourceConnectorError("Connector host is not in the configured allowlist.")
    try:
        resolved = {
            item[4][0]
            for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except OSError:
        raise SourceConnectorError("Connector host could not be resolved.") from None
    if not resolved:
        raise SourceConnectorError("Connector host did not resolve to an address.")
    for value in resolved:
        address = ipaddress.ip_address(value)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            raise SourceConnectorError("Private and local network targets are not allowed.")


def _with_page_parameters(
    url: str, *, page_param: str, page_size_param: str, page: int, page_size: int
) -> str:
    parsed = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {page_param, page_size_param}
    ]
    query.extend(((page_param, str(page)), (page_size_param, str(page_size))))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def _extract_api_records(payload: Any, records_key: str | None) -> list[dict[str, Any]]:
    if records_key:
        for part in records_key.split("."):
            if not isinstance(payload, dict) or part not in payload:
                raise SourceConnectorError("Configured API records path does not exist.")
            payload = payload[part]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise SourceConnectorError(
            "API response must contain an object or an array of objects."
        )
    return payload


async def _fetch_api_page(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None,
    max_bytes: int,
    retry_attempts: int,
) -> tuple[Any, int]:
    for attempt in range(retry_attempts + 1):
        try:
            async with client.stream("GET", url, headers=headers) as response:
                retryable = response.status_code == 429 or 500 <= response.status_code <= 599
                if retryable and attempt < retry_attempts:
                    raw_delay = response.headers.get("retry-after", "")
                    try:
                        delay = min(max(float(raw_delay), 0.0), 5.0)
                    except ValueError:
                        delay = min(0.25 * (2**attempt), 2.0)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                raw_length = response.headers.get("content-length")
                if raw_length:
                    try:
                        if int(raw_length) > max_bytes:
                            raise SourceConnectorError(
                                "API response exceeds the configured size limit."
                            )
                    except ValueError:
                        raise SourceConnectorError(
                            "API response has an invalid content length."
                        ) from None
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise SourceConnectorError(
                            "API response exceeds the configured size limit."
                        )
                    chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks)), total
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SourceConnectorError("API response is not valid JSON.") from None
        except SourceConnectorError:
            raise
        except httpx.HTTPStatusError:
            raise SourceConnectorError(
                "API request failed with a non-retryable HTTP status."
            ) from None
        except httpx.TransportError:
            if attempt >= retry_attempts:
                raise SourceConnectorError(
                    "API request failed after the configured retry attempts."
                ) from None
            await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
    raise SourceConnectorError("API request failed.")


async def fetch_api_records(
    url: str,
    *,
    allowed_hosts: set[str],
    headers: dict[str, str] | None = None,
    records_key: str | None = None,
    timeout_seconds: float = 20,
    max_bytes: int = 10 * 1024 * 1024,
    page_param: str | None = None,
    page_size_param: str | None = None,
    page_size: int = 500,
    start_page: int = 1,
    max_pages: int = 1,
    retry_attempts: int = 2,
    max_records: int = 10_000,
) -> list[dict[str, Any]]:
    """Fetch bounded JSON pages with explicit page-number pagination and retries.

    Pagination is disabled by default. When enabled, both query parameter names
    must be configured. A full final page at max_pages is treated as potentially
    truncated and fails instead of silently importing an incomplete feed.
    """
    _validate_https_url(url, allowed_hosts)
    if not 0 < timeout_seconds <= 60 or not 1 <= max_bytes <= 50 * 1024 * 1024:
        raise SourceConnectorError("API timeout or response-size limit is invalid.")
    if not 1 <= max_pages <= 20 or not 1 <= page_size <= 1000:
        raise SourceConnectorError("API pagination limits are outside the supported bounds.")
    if not 0 <= retry_attempts <= 5:
        raise SourceConnectorError("API retry attempts must be between 0 and 5.")
    if max_pages > 1 and (not page_param or not page_size_param):
        raise SourceConnectorError(
            "Page-number pagination requires explicit page and page-size parameter names."
        )
    if page_param or page_size_param:
        name_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
        if (
            not page_param
            or not page_size_param
            or not name_pattern.fullmatch(page_param)
            or not name_pattern.fullmatch(page_size_param)
            or page_param == page_size_param
        ):
            raise SourceConnectorError("API pagination parameter names are invalid.")
    if start_page < 0:
        raise SourceConnectorError("API start page cannot be negative.")

    all_records: list[dict[str, Any]] = []
    total_bytes = 0
    async with httpx.AsyncClient(
        timeout=timeout_seconds, follow_redirects=False, trust_env=False
    ) as client:
        for page_index in range(max_pages):
            page_number = start_page + page_index
            page_url = (
                _with_page_parameters(
                    url,
                    page_param=page_param,
                    page_size_param=page_size_param,
                    page=page_number,
                    page_size=page_size,
                )
                if page_param and page_size_param
                else url
            )
            _validate_https_url(page_url, allowed_hosts)
            payload, page_bytes = await _fetch_api_page(
                client,
                page_url,
                headers=headers,
                max_bytes=max_bytes - total_bytes,
                retry_attempts=retry_attempts,
            )
            total_bytes += page_bytes
            page_records = _extract_api_records(payload, records_key)
            all_records.extend(page_records)
            if len(all_records) > max_records:
                raise SourceConnectorError(
                    "API source exceeds the configured record limit."
                )
            if max_pages == 1 or len(page_records) < page_size:
                break
            if page_index == max_pages - 1:
                raise SourceConnectorError(
                    "API pagination reached max_pages before a short page; results may be incomplete."
                )
    return all_records


def fetch_sftp_file(
    *,
    host: str,
    port: int,
    username: str,
    password: str | None = None,
    private_key: str | None = None,
    remote_path: str,
    known_hosts_path: str,
    max_bytes: int = 10 * 1024 * 1024,
) -> bytes:
    """Download one file using verified SSH host keys; unknown hosts are rejected."""
    if not known_hosts_path or not remote_path.startswith("/") or "\x00" in remote_path:
        raise SourceConnectorError(
            "An absolute remote path and known-hosts file are required."
        )
    if not username or bool(password) == bool(private_key):
        raise SourceConnectorError(
            "Provide a username and exactly one SFTP authentication method."
        )
    if not 1 <= max_bytes <= 50 * 1024 * 1024:
        raise SourceConnectorError("SFTP file-size limit is invalid.")
    client = None
    try:
        import paramiko

        client = paramiko.SSHClient()
        client.load_host_keys(known_hosts_path)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            key_filename=private_key,
            look_for_keys=False,
            allow_agent=False,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
        )
        with client.open_sftp() as sftp:
            with sftp.open(remote_path, "rb") as remote:
                content = remote.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise SourceConnectorError(
                        "SFTP file exceeds the configured size limit."
                    )
                return content
    except SourceConnectorError:
        raise
    except Exception:
        raise SourceConnectorError(
            "SFTP connection or file retrieval failed; verify credentials and known-hosts configuration."
        ) from None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                raise SourceConnectorError("SFTP session cleanup failed.") from None


def _coerce_watermark(value: str, column: Any) -> Any:
    if not value:
        raise SourceConnectorError("SQL Server watermark value is required.")
    if isinstance(column.type, (Integer, BigInteger)):
        try:
            return int(value)
        except ValueError:
            raise SourceConnectorError("SQL Server watermark must be an integer.") from None
    if isinstance(column.type, Numeric):
        try:
            return Decimal(value)
        except InvalidOperation:
            raise SourceConnectorError("SQL Server watermark must be numeric.") from None
    if isinstance(column.type, DateTime):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise SourceConnectorError(
                "SQL Server datetime watermark must use ISO 8601."
            ) from None
    if isinstance(column.type, Date):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise SourceConnectorError(
                "SQL Server date watermark must use ISO 8601."
            ) from None
    raise SourceConnectorError(
        "SQL Server incremental watermarks require an integer, numeric, date, or datetime column."
    )


def fetch_sql_server_rows(
    connection_url: str,
    *,
    schema: str,
    table: str,
    columns: list[str],
    limit: int = 10_000,
    max_bytes: int = 10 * 1024 * 1024,
    watermark_column: str | None = None,
    watermark_after: str | None = None,
) -> list[dict[str, Any]]:
    """Read a bounded, SELECT-only SQL Server projection.

    Incremental extraction is supported only for a selected, unique numeric/date
    watermark column. The caller supplies the last committed value; the returned
    rows include the watermark so the next checkpoint can be reviewed and saved.
    """
    if not connection_url.startswith("mssql+pyodbc://"):
        raise SourceConnectorError(
            "SQL Server requires a mssql+pyodbc connection URL and configured ODBC driver."
        )
    try:
        parsed_url = make_url(connection_url)
    except Exception:
        raise SourceConnectorError("SQL Server connection URL is invalid.") from None
    if not parsed_url.username or not parsed_url.password:
        raise SourceConnectorError(
            "SQL Server requires a dedicated SQL-authenticated read-only login; integrated authentication is not accepted."
        )
    query = parsed_url.query
    odbc_connect = unquote_plus(str(query.get("odbc_connect", "")))
    connection_options = ";".join(
        [f"{key}={value}" for key, value in query.items()] + [odbc_connect]
    )
    if "ODBC Driver 18" not in connection_options:
        raise SourceConnectorError(
            "SQL Server must use Microsoft ODBC Driver 18."
        )
    if not re.search(r"Encrypt\s*=\s*(yes|true)", connection_options, re.IGNORECASE):
        raise SourceConnectorError("SQL Server connections must enable encryption.")
    if not re.search(
        r"TrustServerCertificate\s*=\s*(no|false)",
        connection_options,
        re.IGNORECASE,
    ):
        raise SourceConnectorError(
            "SQL Server certificate verification must remain enabled."
        )
    if not re.search(
        r"ApplicationIntent\s*=\s*ReadOnly", connection_options, re.IGNORECASE
    ):
        raise SourceConnectorError(
            "SQL Server connections must declare ApplicationIntent=ReadOnly."
        )
    identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    if not identifier.fullmatch(schema) or not identifier.fullmatch(table):
        raise SourceConnectorError("Invalid SQL Server schema or table identifier.")
    if (
        not columns
        or len(columns) > 200
        or any(not identifier.fullmatch(col) for col in columns)
        or len(set(columns)) != len(columns)
    ):
        raise SourceConnectorError(
            "Provide 1 to 200 unique, valid column identifiers."
        )
    if not 1 <= limit <= 10_000:
        raise SourceConnectorError(
            "SQL Server row limit must be between 1 and 10,000."
        )
    if bool(watermark_column) != bool(watermark_after):
        raise SourceConnectorError(
            "Configure both a SQL Server watermark column and its last committed value."
        )
    if watermark_column and (
        not identifier.fullmatch(watermark_column) or watermark_column not in columns
    ):
        raise SourceConnectorError(
            "The SQL Server watermark column must be a valid selected column."
        )

    if "ODBC Driver 18 for SQL Server" not in pyodbc.drivers():
        raise SourceConnectorError(
            "Microsoft ODBC Driver 18 for SQL Server is not installed in this runtime."
        )

    try:
        engine = create_engine(
            connection_url, pool_pre_ping=True, pool_size=1, max_overflow=0
        )
        try:
            with engine.connect() as connection:
                source_table = Table(
                    table, MetaData(), schema=schema, autoload_with=connection
                )
                selected_columns = [source_table.c[column] for column in columns]
                statement = select(*selected_columns)
                if watermark_column:
                    watermark = source_table.c[watermark_column]
                    unique_watermark = watermark.primary_key or any(
                        isinstance(constraint, UniqueConstraint)
                        and len(constraint.columns) == 1
                        and watermark.name in constraint.columns
                        for constraint in source_table.constraints
                    )
                    if not unique_watermark:
                        raise SourceConnectorError(
                            "Incremental watermark must be a unique or primary-key column to avoid skipped tied values."
                        )
                    watermark_value = _coerce_watermark(watermark_after, watermark)
                    statement = statement.where(watermark > watermark_value)
                    statement = statement.order_by(watermark.asc())
                statement = statement.limit(limit)
                rows = [
                    dict(row)
                    for row in connection.execute(statement).mappings().all()
                ]
                if (
                    len(
                        json.dumps(rows, ensure_ascii=False, default=str).encode(
                            "utf-8"
                        )
                    )
                    > max_bytes
                ):
                    raise SourceConnectorError(
                        "SQL Server result exceeds the configured size limit."
                    )
                return rows
        finally:
            engine.dispose()
    except SourceConnectorError:
        raise
    except Exception:
        raise SourceConnectorError(
            "SQL Server read failed; verify the dedicated read-only login, ODBC Driver 18, and source schema."
        ) from None
