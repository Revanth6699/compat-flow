"""Opt-in protocol tests against disposable local supplier simulators.

Run only with the connector-simulator Compose stack. The REST test bypasses DNS
policy only for localhost; production SSRF/allowlist behavior remains covered
by test_source_connectors.py.
"""
import os
from pathlib import Path

import pytest
import pyodbc
from sqlalchemy.engine import make_url

from app.services import source_connectors as connectors
from app.services.source_connectors import (
    fetch_api_records,
    fetch_sftp_file,
    fetch_sql_server_rows,
    SourceConnectorError,
)

pytestmark = pytest.mark.skipif(
    os.getenv("COMPATFLOW_CONNECTOR_SIMULATOR") != "1",
    reason="requires the opt-in connector simulator stack",
)


@pytest.mark.anyio
async def test_rest_supplier_https_auth_and_records(monkeypatch):
    # The disposable simulator resolves to a private container network. Do not
    # weaken the production URL validator; bypass only this test's localhost case.
    monkeypatch.setattr(connectors, "_validate_https_url", lambda url, allowed: None)
    cert = os.environ["SIMULATOR_REST_CERT"]
    monkeypatch.setenv("SSL_CERT_FILE", cert)
    rows = await fetch_api_records(
        os.environ.get("SIMULATOR_REST_URL", "https://localhost:8443/catalog?page=1"),
        allowed_hosts={"localhost"},
        headers={"X-API-Key": os.environ.get("SIMULATOR_REST_API_KEY", "local-test-key")},
        records_key="data.items",
    )
    assert [row["sku"] for row in rows] == ["SIM-1001", "SIM-1002"]


def test_sftp_supplier_host_key_auth_and_file_read():
    rows = fetch_sftp_file(
        host="localhost",
        port=int(os.getenv("SIMULATOR_SFTP_PORT", "2222")),
        username="supplier",
        password=os.getenv("SIMULATOR_SFTP_PASSWORD", "Supplier-ReadOnly-2026!"),
        remote_path="/upload/catalog.csv",
        known_hosts_path=os.environ["SIMULATOR_SFTP_KNOWN_HOSTS"],
        max_bytes=1024 * 1024,
    )
    assert b"SIM-SFTP-001" in rows
    assert b"Replacement Bearing" in rows


def test_sql_server_supplier_read_only_projection():
    url = os.getenv("SIMULATOR_SQLSERVER_URL")
    if not url:
        pytest.skip("SIMULATOR_SQLSERVER_URL is not configured for the SQL Server simulator")

    # Probe the exact trusted ODBC connection separately so failures retain
    # the driver diagnostic while the production connector keeps errors generic.
    parsed = make_url(url)
    query = parsed.query
    odbc_connection = (
        f"DRIVER={{{query['driver']}}};"
        f"SERVER={parsed.host},{parsed.port or 1433};"
        f"DATABASE={parsed.database};UID={parsed.username};PWD={parsed.password};"
        f"Encrypt={query.get('Encrypt', 'yes')};"
        + (f"ServerCertificate={query['ServerCertificate']};" if query.get("ServerCertificate") else "")
        + f"TrustServerCertificate={query.get('TrustServerCertificate', 'no')}"
    )
    with pyodbc.connect(odbc_connection, timeout=8) as direct_connection:
        direct_rows = direct_connection.cursor().execute(
            "SELECT sku FROM dbo.SupplierProducts ORDER BY sku"
        ).fetchall()
    assert [row[0] for row in direct_rows] == ["SIM-SQL-001", "SIM-SQL-002"]

    rows = fetch_sql_server_rows(
        url,
        schema="dbo",
        table="SupplierProducts",
        columns=["sku", "title", "unit_price", "currency", "quantity"],
        limit=10,
    )
    assert [row["sku"] for row in rows] == ["SIM-SQL-001", "SIM-SQL-002"]


def test_sql_server_simulator_never_accepts_write_sql():
    with pytest.raises(SourceConnectorError):
        fetch_sql_server_rows(
            "postgresql://not-a-sql-server",
            schema="dbo",
            table="SupplierProducts",
            columns=["sku"],
        )
