"""Secure, bounded source connector primitives for catalog ingestion.

Connector credentials are request-scoped. This module never persists or logs them.
REST pagination is explicit page-number pagination; supplier-specific cursor
protocols require a dedicated adapter rather than guessing response semantics.
"""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import io
import json
import re
import socket
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlencode, unquote_plus, urlsplit, urlunsplit

import aiohttp
import ssl
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


def _normalize_hostname(host: str) -> str:
    try:
        return ipaddress.ip_address(host).compressed.casefold()
    except ValueError:
        try:
            return host.encode("idna").decode("ascii").casefold().rstrip(".")
        except UnicodeError:
            raise SourceConnectorError("Connector hostname is invalid.") from None


def _resolve_public_addresses(host: str, port: int) -> list[str]:
    """Resolve once and reject every address that is not globally routable."""
    try:
        resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise SourceConnectorError("Connector host could not be resolved.") from None
    addresses: set[str] = set()
    for item in resolved:
        try:
            address = ipaddress.ip_address(item[4][0].split("%", 1)[0])
        except (IndexError, ValueError):
            raise SourceConnectorError("Connector host returned an invalid network address.") from None
        if not address.is_global:
            raise SourceConnectorError("Private and local network targets are not allowed.")
        addresses.add(address.compressed)
    if not addresses:
        raise SourceConnectorError("Connector host did not resolve to an address.")
    if len(addresses) > 16:
        raise SourceConnectorError("Connector host returned too many network addresses.")
    return sorted(
        addresses,
        key=lambda value: (
            ipaddress.ip_address(value).version,
            int(ipaddress.ip_address(value)),
        ),
    )


def _resolve_https_target(url: str, allowed_hosts: set[str]) -> tuple[str, int, list[str]]:
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise SourceConnectorError("Connector URL is invalid.") from None
    try:
        port = parsed.port or 443
    except ValueError:
        raise SourceConnectorError("Connector URL contains an invalid port.") from None
    sensitive_query_names = {
        "api_key", "apikey", "access_token", "token", "password",
        "client_secret", "secret", "authorization", "signature", "auth",
        "credential", "x_api_key", "key", "accesskey", "secretkey", "auth_token",
        "refresh_token", "client_assertion", "awsaccesskeyid", "x_amz_credential",
        "x_amz_signature", "x_goog_signature", "sig", "se", "sp", "sv", "sr", "st",
        "code", "jwt", "subscription_key", "ocp_apim_subscription_key",
    }
    if any(
        name.casefold().replace("-", "_") in sensitive_query_names
        for name, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise SourceConnectorError(
            "Credentials in API query parameters are not allowed; use an Authorization or X-API-Key header."
        )
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
    host = _normalize_hostname(parsed.hostname)
    allowed = {_normalize_hostname(item) for item in allowed_hosts}
    if host not in allowed:
        raise SourceConnectorError("Connector host is not in the configured allowlist.")
    addresses = _resolve_public_addresses(parsed.hostname, port)
    return host, port, addresses


def _validate_https_url(url: str, allowed_hosts: set[str]) -> None:
    """Validate URL and DNS answers without making an outbound request."""
    _resolve_https_target(url, allowed_hosts)


class _PinnedResolver(aiohttp.abc.AbstractResolver):
    """aiohttp resolver that can only return the addresses validated for one host."""

    def __init__(self, hostname: str, port: int, addresses: list[str]) -> None:
        self.hostname = _normalize_hostname(hostname)
        self.port = port
        self.addresses = tuple(addresses)

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[dict[str, Any]]:
        if _normalize_hostname(host) != self.hostname or port != self.port:
            raise OSError("Connector attempted to resolve an unvalidated target.")
        results: list[dict[str, Any]] = []
        for value in self.addresses:
            address = ipaddress.ip_address(value)
            address_family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
            if family not in (socket.AF_UNSPEC, address_family):
                continue
            results.append(
                {
                    "hostname": host,
                    "host": address.compressed,
                    "port": port,
                    "family": address_family,
                    "proto": socket.IPPROTO_TCP,
                    "flags": socket.AI_NUMERICHOST,
                }
            )
        if not results:
            raise OSError("No validated connector address matches the requested address family.")
        return results

    async def close(self) -> None:
        return None


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
    client: aiohttp.ClientSession,
    url: str,
    *,
    headers: dict[str, str] | None,
    max_bytes: int,
    retry_attempts: int,
) -> tuple[Any, int]:
    for attempt in range(retry_attempts + 1):
        try:
            async with client.get(
                url, headers=headers, allow_redirects=False
            ) as response:
                status = response.status
                retryable = status == 429 or 500 <= status <= 599
                if retryable:
                    if attempt >= retry_attempts:
                        raise SourceConnectorError(
                            "API request failed after the configured retry attempts."
                        )
                    raw_delay = response.headers.get("retry-after", "")
                    try:
                        delay = min(max(float(raw_delay), 0.0), 5.0)
                    except (TypeError, ValueError):
                        delay = min(0.25 * (2**attempt), 2.0)
                    await asyncio.sleep(delay)
                    continue
                if 300 <= status <= 399:
                    raise SourceConnectorError("API redirects are not allowed.")
                if status >= 400:
                    raise SourceConnectorError(
                        "API request failed with a non-retryable HTTP status."
                    )
                raw_length = response.headers.get("content-length")
                if raw_length:
                    try:
                        declared_length = int(raw_length)
                        if declared_length < 0 or declared_length > max_bytes:
                            raise SourceConnectorError(
                                "API response exceeds the configured size limit."
                            )
                    except ValueError:
                        raise SourceConnectorError(
                            "API response has an invalid content length."
                        ) from None
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise SourceConnectorError(
                            "API response exceeds the configured size limit."
                        )
                    chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks)), total
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                raise SourceConnectorError(
                    "API response is not valid or exceeds the supported JSON nesting depth."
                ) from None
        except SourceConnectorError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError):
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
    """Fetch bounded JSON pages with pinned DNS, explicit pagination, and retries.

    The validated DNS answers are pinned into the HTTP resolver for this run.
    TLS verification and the HTTP Host header still use the original URL hostname.
    Pagination is disabled by default. A full final page at max_pages fails rather
    than silently importing an incomplete feed.
    """
    host, port, addresses = _resolve_https_target(url, allowed_hosts)
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
    resolver = _PinnedResolver(host, port, addresses)
    connector = aiohttp.TCPConnector(
        resolver=resolver,
        use_dns_cache=True,
        ttl_dns_cache=300,
        family=socket.AF_UNSPEC,
        ssl=ssl.create_default_context(),
        limit=10,
    )
    timeout = aiohttp.ClientTimeout(
        total=timeout_seconds, connect=min(timeout_seconds, 10)
    )
    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, trust_env=False
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
            remaining_bytes = max_bytes - total_bytes
            if remaining_bytes <= 0:
                raise SourceConnectorError(
                    "API source reached the configured total response-size limit."
                )
            payload, page_bytes = await _fetch_api_page(
                client,
                page_url,
                headers=headers,
                max_bytes=remaining_bytes,
                retry_attempts=retry_attempts,
            )
            total_bytes += page_bytes
            page_records = _extract_api_records(payload, records_key)
            all_records.extend(page_records)
            if len(all_records) > max_records:
                raise SourceConnectorError(
                    "API source exceeds the configured record limit."
                )
            if page_param and max_pages == 1 and len(page_records) >= page_size:
                raise SourceConnectorError(
                    "API page is full; configure a larger max_pages value to avoid an incomplete import."
                )
            if max_pages == 1 or len(page_records) < page_size:
                break
            if page_index == max_pages - 1:
                raise SourceConnectorError(
                    "API pagination reached max_pages before a short page; results may be incomplete."
                )
    return all_records


def _load_sftp_private_key(private_key: str, paramiko: Any) -> Any:
    """Parse pasted, unencrypted PEM/OpenSSH key material without using a file path."""
    value = private_key.strip()
    if len(value) > 64 * 1024:
        raise SourceConnectorError("SFTP private key exceeds the supported size limit.")
    first_line = value.splitlines()[0] if value else ""
    if not first_line.startswith("-----BEGIN ") or "PRIVATE KEY-----" not in first_line:
        raise SourceConnectorError(
            "SFTP private-key authentication requires pasted PEM/OpenSSH private-key content."
        )

    key_types = (
        getattr(paramiko, "Ed25519Key", None),
        getattr(paramiko, "ECDSAKey", None),
        getattr(paramiko, "RSAKey", None),
    )
    parse_failures = 0
    for key_type in key_types:
        if key_type is None:
            continue
        try:
            return key_type.from_private_key(io.StringIO(value))
        except (paramiko.SSHException, ValueError, TypeError):
            parse_failures += 1
    if parse_failures == 0:
        raise SourceConnectorError("SFTP private-key parsing is unavailable.")
    raise SourceConnectorError(
        "SFTP private key is invalid, encrypted, or uses an unsupported key type."
    ) from None


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
    """Download one file over SSH using pinned public DNS and strict host keys."""
    path_parts = remote_path.split("/")
    if (
        not known_hosts_path
        or not remote_path.startswith("/")
        or "\x00" in remote_path
        or any(part in {".", ".."} for part in path_parts)
    ):
        raise SourceConnectorError(
            "An absolute remote path without dot segments and a known-hosts file are required."
        )
    if not username or bool(password) == bool(private_key):
        raise SourceConnectorError(
            "Provide a username and exactly one SFTP authentication method."
        )
    if not 1 <= port <= 65535 or not 1 <= max_bytes <= 50 * 1024 * 1024:
        raise SourceConnectorError("SFTP port or file-size limit is invalid.")
    client = None
    connection = None
    try:
        import paramiko

        parsed_key = _load_sftp_private_key(private_key, paramiko) if private_key else None
        addresses = _resolve_public_addresses(host, port)
        last_connect_error: OSError | None = None
        for address in addresses:
            try:
                connection = socket.create_connection((address, port), timeout=15)
                break
            except OSError as exc:
                last_connect_error = exc
        if connection is None:
            raise SourceConnectorError(
                "SFTP host could not be reached at its validated public addresses."
            ) from last_connect_error

        client = paramiko.SSHClient()
        client.load_host_keys(known_hosts_path)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            hostname=host,
            port=port,
            sock=connection,
            username=username,
            password=password,
            pkey=parsed_key,
            key_filename=None,
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
            with contextlib.suppress(Exception):
                client.close()
        if connection is not None:
            with contextlib.suppress(OSError):
                connection.close()


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
    if not 1 <= max_bytes <= 50 * 1024 * 1024:
        raise SourceConnectorError("SQL Server result-size limit is invalid.")
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
                    primary_key_columns = list(source_table.primary_key.columns)
                    unique_watermark = (
                        len(primary_key_columns) == 1
                        and primary_key_columns[0].name == watermark.name
                    ) or any(
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
                # Fetch one extra row so reaching the configured cap is not
                # mistaken for a complete extraction when more source rows exist.
                statement = statement.limit(limit + 1)
                result = connection.execute(statement).mappings().yield_per(500)
                rows: list[dict[str, Any]] = []
                total_bytes = 2  # JSON array delimiters.
                for row in result:
                    if len(rows) >= limit:
                        raise SourceConnectorError(
                            "SQL Server result reached the configured row limit; results may be incomplete."
                        )
                    item = dict(row)
                    encoded_size = len(
                        json.dumps(item, ensure_ascii=False, default=str).encode("utf-8")
                    )
                    total_bytes += encoded_size + (1 if rows else 0)
                    if total_bytes > max_bytes:
                        raise SourceConnectorError(
                            "SQL Server result exceeds the configured size limit."
                        )
                    rows.append(item)
                return rows
        finally:
            engine.dispose()
    except SourceConnectorError:
        raise
    except Exception:
        raise SourceConnectorError(
            "SQL Server read failed; verify the dedicated read-only login, ODBC Driver 18, and source schema."
        ) from None
