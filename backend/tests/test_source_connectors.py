import sys
from types import SimpleNamespace

import pytest

from app.services import source_connectors as connectors
from app.services.source_connectors import (
    SourceConnectorError,
    _validate_https_url,
    fetch_api_records,
    fetch_sftp_file,
    fetch_sql_server_rows,
)


def test_api_connector_requires_https_and_allowlisted_host(monkeypatch):
    monkeypatch.setattr(
        "app.services.source_connectors.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    _validate_https_url("https://supplier.example/api", {"supplier.example"})
    with pytest.raises(SourceConnectorError, match="HTTPS"):
        _validate_https_url("http://supplier.example/api", {"supplier.example"})
    with pytest.raises(SourceConnectorError, match="allowlist"):
        _validate_https_url("https://other.example/api", {"supplier.example"})


def test_api_connector_rejects_embedded_credentials():
    with pytest.raises(SourceConnectorError):
        _validate_https_url("https://user:password@supplier.example/api", {"supplier.example"})


@pytest.mark.asyncio
async def test_api_connector_fetches_and_extracts_records_path(monkeypatch):
    class Response:
        headers = {"content-length": "30"}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            yield b'{"data":{"items":[{"sku":"001"}]}}'

    class Client:
        def __init__(self, **kwargs):
            self.options = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, headers=None):
            assert method == "GET"
            assert url == "https://supplier.example/catalog"
            assert headers == {"X-API-Key": "secret"}
            return Response()

    monkeypatch.setattr(connectors, "_validate_https_url", lambda *args: None)
    monkeypatch.setattr(connectors.httpx, "AsyncClient", Client)
    records = await fetch_api_records(
        "https://supplier.example/catalog",
        allowed_hosts={"supplier.example"},
        headers={"X-API-Key": "secret"},
        records_key="data.items",
    )
    assert records == [{"sku": "001"}]


@pytest.mark.asyncio
async def test_api_connector_rejects_non_object_records(monkeypatch):
    class Response:
        headers = {}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            yield b'[1,2,3]'

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(connectors, "_validate_https_url", lambda *args: None)
    monkeypatch.setattr(connectors.httpx, "AsyncClient", Client)
    with pytest.raises(SourceConnectorError, match="array of objects"):
        await fetch_api_records("https://supplier.example/catalog", allowed_hosts={"supplier.example"})


def test_sftp_connector_downloads_with_known_host_verification(monkeypatch):
    calls = {}

    class RemoteFile:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            calls["read_size"] = size
            return b"SKU,Name\\n001,Widget"

    class SFTP:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def open(self, path, mode):
            calls["remote"] = (path, mode)
            return RemoteFile()

    class Client:
        def load_host_keys(self, path):
            calls["known_hosts"] = path

        def set_missing_host_key_policy(self, policy):
            calls["policy"] = policy

        def connect(self, **kwargs):
            calls["connect"] = kwargs

        def open_sftp(self):
            return SFTP()

        def close(self):
            calls["closed"] = True

    class Paramiko:
        RejectPolicy = lambda self: "reject-unknown-host"
        SSHClient = Client

    monkeypatch.setitem(sys.modules, "paramiko", Paramiko())
    result = fetch_sftp_file(
        host="sftp.supplier.example", port=22, username="reader",
        password="secret", remote_path="/exports/catalog.csv",
        known_hosts_path="/run/secrets/known_hosts", max_bytes=100,
    )
    assert result == b"SKU,Name\\n001,Widget"
    assert calls["known_hosts"] == "/run/secrets/known_hosts"
    assert calls["policy"] == "reject-unknown-host"
    assert calls["remote"] == ("/exports/catalog.csv", "rb")
    assert calls["connect"]["look_for_keys"] is False
    assert calls["closed"] is True


def test_sftp_connector_rejects_unknown_host_key(monkeypatch):
    class Client:
        def load_host_keys(self, path):
            pass

        def set_missing_host_key_policy(self, policy):
            pass

        def connect(self, **kwargs):
            raise RuntimeError("unknown host key")

        def close(self):
            pass

    class Paramiko:
        RejectPolicy = lambda self: "reject"
        SSHClient = Client

    monkeypatch.setitem(sys.modules, "paramiko", Paramiko())
    with pytest.raises(SourceConnectorError, match="SFTP connection"):
        fetch_sftp_file(
            host="sftp.supplier.example", port=22, username="reader",
            password="secret", remote_path="/catalog.csv",
            known_hosts_path="/known_hosts",
        )


def test_sql_server_connector_rejects_non_sql_server_urls():
    with pytest.raises(SourceConnectorError, match="mssql"):
        fetch_sql_server_rows("postgresql://example/db", schema="dbo",
                              table="Products", columns=["sku"])


@pytest.mark.parametrize("identifier", ["Products; DROP TABLE Users", "dbo.Products", "bad-name"])
def test_sql_server_connector_rejects_unsafe_table_identifiers(identifier):
    with pytest.raises(SourceConnectorError, match="identifier"):
        fetch_sql_server_rows(
            "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no",
            schema="dbo", table=identifier, columns=["sku"],
        )


def test_sql_server_connector_requires_encryption_and_certificate_validation():
    with pytest.raises(SourceConnectorError, match="encryption"):
        fetch_sql_server_rows(
            "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server",
            schema="dbo", table="Products", columns=["sku"],
        )


def test_sql_server_connector_reads_only_selected_bounded_columns(monkeypatch):
    calls = {}

    class ColumnCollection:
        def __getitem__(self, name):
            calls.setdefault("selected", []).append(name)
            return name

    class FakeTable:
        c = ColumnCollection()

    class Statement:
        def limit(self, value):
            calls["limit"] = value
            return self

    class MappingResult:
        def all(self):
            return [{"sku": "001", "name": "Widget"}]

    class ExecutionResult:
        def mappings(self):
            return MappingResult()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            calls["executed"] = True
            return ExecutionResult()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            calls["disposed"] = True

    def fake_table(table, metadata, schema, autoload_with):
        calls["table"] = (schema, table)
        return FakeTable()

    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", fake_table)
    monkeypatch.setattr(connectors, "MetaData", lambda: object())
    monkeypatch.setattr(connectors, "select", lambda *columns: Statement())

    rows = fetch_sql_server_rows(
        "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no",
        schema="dbo", table="Products", columns=["sku", "name"], limit=25,
    )
    assert rows == [{"sku": "001", "name": "Widget"}]
    assert calls["table"] == ("dbo", "Products")
    assert calls["selected"] == ["sku", "name"]
    assert calls["limit"] == 25
    assert calls["executed"] is True
    assert calls["disposed"] is True
