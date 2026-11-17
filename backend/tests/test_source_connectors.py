import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table as SQLTable

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


def _patch_api_http(monkeypatch, response_factory):
    calls = {"requests": []}

    class Content:
        def __init__(self, payload):
            self.payload = payload

        async def iter_chunked(self, size):
            calls["chunk_size"] = size
            if self.payload:
                yield self.payload

    class Response:
        def __init__(self, status, payload, headers=None):
            self.status = status
            self.headers = headers or {}
            self.content = Content(payload)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class Session:
        def __init__(self, **kwargs):
            calls["session_options"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url, headers=None, allow_redirects=True):
            calls["requests"].append(
                {"url": url, "headers": headers, "allow_redirects": allow_redirects}
            )
            return response_factory(url)

    class Connector:
        def __init__(self, **kwargs):
            calls["connector_options"] = kwargs

    monkeypatch.setattr(connectors.aiohttp, "ClientSession", Session)
    monkeypatch.setattr(connectors.aiohttp, "TCPConnector", Connector)
    monkeypatch.setattr(
        connectors,
        "_resolve_https_target",
        lambda url, allowed: ("supplier.example", 443, ["93.184.216.34"]),
    )
    return calls, Response


@pytest.mark.anyio
async def test_api_connector_fetches_records_and_pins_validated_dns(monkeypatch):
    def response_factory(url):
        return Response(200, b'{"data":{"items":[{"sku":"001"}]}}', {"content-length": "38"})

    calls, Response = _patch_api_http(monkeypatch, response_factory)
    records = await fetch_api_records(
        "https://supplier.example/catalog",
        allowed_hosts={"supplier.example"},
        headers={"X-API-Key": "secret"},
        records_key="data.items",
    )
    assert records == [{"sku": "001"}]
    assert calls["session_options"]["trust_env"] is False
    assert calls["requests"][0]["allow_redirects"] is False
    assert calls["requests"][0]["headers"] == {"X-API-Key": "secret"}
    resolver = calls["connector_options"]["resolver"]
    assert isinstance(resolver, connectors._PinnedResolver)
    pinned = await resolver.resolve("supplier.example", 443, socket.AF_UNSPEC)
    assert [item["host"] for item in pinned] == ["93.184.216.34"]
    with pytest.raises(OSError, match="unvalidated target"):
        await resolver.resolve("other.example", 443, socket.AF_UNSPEC)


@pytest.mark.anyio
async def test_api_connector_rejects_non_object_records(monkeypatch):
    calls, Response = _patch_api_http(
        monkeypatch, lambda url: Response(200, b"[1,2,3]")
    )
    with pytest.raises(SourceConnectorError, match="array of objects"):
        await fetch_api_records(
            "https://supplier.example/catalog",
            allowed_hosts={"supplier.example"},
        )


@pytest.mark.anyio
async def test_api_connector_rejects_redirects(monkeypatch):
    calls, Response = _patch_api_http(
        monkeypatch, lambda url: Response(302, b"", {"location": "http://127.0.0.1"})
    )
    with pytest.raises(SourceConnectorError, match="redirects are not allowed"):
        await fetch_api_records(
            "https://supplier.example/catalog",
            allowed_hosts={"supplier.example"},
        )


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
        def RejectPolicy(self):
            return "reject-unknown-host"

        SSHClient = Client

    class FakeSocket:
        def close(self):
            calls["socket_closed"] = True

    monkeypatch.setattr(
        connectors.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 22))],
    )
    monkeypatch.setattr(
        connectors.socket,
        "create_connection",
        lambda address, timeout: (calls.setdefault("socket_target", address) or FakeSocket()),
    )
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
    assert calls["connect"]["hostname"] == "sftp.supplier.example"
    assert calls["connect"]["sock"] is not None
    assert calls["socket_target"] == ("93.184.216.34", 22)
    assert calls["socket_closed"] is True
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
        def RejectPolicy(self):
            return "reject"

        SSHClient = Client

    class FakeSocket:
        def close(self):
            pass

    monkeypatch.setattr(
        connectors.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 22))],
    )
    monkeypatch.setattr(
        connectors.socket, "create_connection", lambda *args, **kwargs: FakeSocket()
    )
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
            "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
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
        def yield_per(self, size):
            calls["yield_per"] = size
            return self

        def __iter__(self):
            return iter([{"sku": "001", "name": "Widget"}])

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

    monkeypatch.setattr(connectors.pyodbc, "drivers", lambda: ["ODBC Driver 18 for SQL Server"])
    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", fake_table)
    monkeypatch.setattr(connectors, "MetaData", lambda: object())
    monkeypatch.setattr(connectors, "select", lambda *columns: Statement())

    rows = fetch_sql_server_rows(
        "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
        schema="dbo", table="Products", columns=["sku", "name"], limit=25,
    )
    assert rows == [{"sku": "001", "name": "Widget"}]
    assert calls["table"] == ("dbo", "Products")
    assert calls["selected"] == ["sku", "name"]
    assert calls["limit"] == 26
    assert calls["executed"] is True
    assert calls["disposed"] is True



def test_api_connector_rejects_private_dns_targets(monkeypatch):
    monkeypatch.setattr(
        "app.services.source_connectors.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    with pytest.raises(SourceConnectorError, match="Private and local"):
        _validate_https_url("https://supplier.example/api", {"supplier.example"})


def test_api_connector_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    monkeypatch.setattr(
        connectors.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (None, None, None, None, ("93.184.216.34", 443)),
            (None, None, None, None, ("10.0.0.8", 443)),
        ],
    )
    with pytest.raises(SourceConnectorError, match="Private and local"):
        _validate_https_url(
            "https://supplier.example/api", {"supplier.example"}
        )


def test_api_connector_rejects_invalid_url_port():
    with pytest.raises(SourceConnectorError, match="invalid port"):
        _validate_https_url("https://supplier.example:bad/api", {"supplier.example"})


def test_sql_server_connector_enforces_serialized_result_byte_limit(monkeypatch):
    calls = {"yielded": 0}

    class ColumnCollection:
        def __getitem__(self, name):
            return name

    class FakeTable:
        c = ColumnCollection()

    class Statement:
        def limit(self, value):
            return self

    class MappingResult:
        def yield_per(self, size):
            calls["batch_size"] = size
            return self

        def __iter__(self):
            calls["yielded"] += 1
            yield {"sku": "001", "description": "x" * 100}
            calls["yielded"] += 1
            yield {"sku": "002", "description": "another row"}

    class ExecutionResult:
        def mappings(self):
            return MappingResult()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            return ExecutionResult()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(connectors.pyodbc, "drivers", lambda: ["ODBC Driver 18 for SQL Server"])
    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", lambda *args, **kwargs: FakeTable())
    monkeypatch.setattr(connectors, "MetaData", lambda: object())
    monkeypatch.setattr(connectors, "select", lambda *columns: Statement())

    with pytest.raises(SourceConnectorError, match="size limit"):
        fetch_sql_server_rows(
            "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
            schema="dbo", table="Products", columns=["sku", "description"],
            limit=10, max_bytes=20,
        )
    assert calls["yielded"] == 1
    assert calls["batch_size"] == 500



@pytest.mark.anyio
async def test_api_connector_fetches_explicit_page_number_pagination(monkeypatch):
    def response_factory(url):
        if "page=4" in url:
            return Response(200, b'{"items":[{"sku":"A"}]}')
        return Response(200, b'{"items":[]}')

    calls, Response = _patch_api_http(monkeypatch, response_factory)
    records = await fetch_api_records(
        "https://supplier.example/catalog?tenant=demo",
        allowed_hosts={"supplier.example"},
        records_key="items",
        page_param="page",
        page_size_param="limit",
        page_size=1,
        start_page=4,
        max_pages=3,
    )
    assert records == [{"sku": "A"}]
    assert "page=4" in calls["requests"][0]["url"]
    assert "limit=1" in calls["requests"][0]["url"]
    assert "tenant=demo" in calls["requests"][0]["url"]
    assert "page=5" in calls["requests"][1]["url"]


@pytest.mark.anyio
async def test_api_connector_retries_transient_server_errors(monkeypatch):
    attempts = {"count": 0}
    delays = []

    def response_factory(url):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return Response(503, b"temporary", {"retry-after": "0"})
        return Response(200, b'[{"sku":"001"}]')

    calls, Response = _patch_api_http(monkeypatch, response_factory)

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(connectors.asyncio, "sleep", fake_sleep)
    records = await fetch_api_records(
        "https://supplier.example/catalog",
        allowed_hosts={"supplier.example"},
        retry_attempts=2,
    )
    assert records == [{"sku": "001"}]
    assert attempts["count"] == 2
    assert delays == [0.0]


@pytest.mark.anyio
async def test_api_connector_fails_instead_of_silently_truncating_full_pages(monkeypatch):
    calls, Response = _patch_api_http(
        monkeypatch, lambda url: Response(200, b'[{"sku":"001"}]')
    )
    with pytest.raises(SourceConnectorError, match="may be incomplete"):
        await fetch_api_records(
            "https://supplier.example/catalog",
            allowed_hosts={"supplier.example"},
            page_param="page",
            page_size_param="limit",
            page_size=1,
            max_pages=2,
        )


def test_sql_server_connector_requires_installed_microsoft_driver_18(monkeypatch):
    monkeypatch.setattr(connectors.pyodbc, "drivers", lambda: [])
    with pytest.raises(SourceConnectorError, match="not installed"):
        fetch_sql_server_rows(
            "mssql+pyodbc://reader:secret@sql.example/catalog?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
            schema="dbo",
            table="Products",
            columns=["sku"],
        )


def test_sql_server_incremental_watermark_requires_selected_unique_column(monkeypatch):
    monkeypatch.setattr(connectors.pyodbc, "drivers", lambda: ["ODBC Driver 18 for SQL Server"])

    class Column:
        name = "modified_id"
        primary_key = False
        type = connectors.Integer()

        def __gt__(self, value):
            calls["watermark"] = value
            return ("greater_than", value)

        def asc(self):
            return "ascending"

    class ColumnCollection:
        def __getitem__(self, name):
            if name == "modified_id":
                return Column()
            return name

    class FakeTable:
        c = ColumnCollection()
        constraints = set()
        primary_key = SimpleNamespace(columns=[])
    class Statement:
        def where(self, clause):
            calls["where"] = clause
            return self

        def order_by(self, clause):
            calls["order_by"] = clause
            return self

        def limit(self, value):
            calls["limit"] = value
            return self

    calls = {}

    class MappingResult:
        def yield_per(self, size):
            calls["yield_per"] = size
            return self

        def __iter__(self):
            return iter([{"modified_id": 11, "sku": "001"}])

    class ExecutionResult:
        def mappings(self):
            return MappingResult()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            return ExecutionResult()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", lambda *args, **kwargs: FakeTable())
    monkeypatch.setattr(connectors, "MetaData", lambda: object())
    monkeypatch.setattr(connectors, "select", lambda *columns: Statement())

    with pytest.raises(SourceConnectorError, match="unique or primary-key"):
        fetch_sql_server_rows(
            "mssql+pyodbc://reader:secret@sql.example/catalog?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
            schema="dbo",
            table="Products",
            columns=["modified_id", "sku"],
            watermark_column="modified_id",
            watermark_after="10",
        )


def test_sql_server_incremental_watermark_rejects_unselected_column():
    with pytest.raises(SourceConnectorError, match="selected column"):
        fetch_sql_server_rows(
            "mssql+pyodbc://reader:secret@sql.example/catalog?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
            schema="dbo",
            table="Products",
            columns=["sku"],
            watermark_column="modified_id",
            watermark_after="10",
        )



def test_sql_server_incremental_watermark_uses_unique_numeric_key_and_ordered_select(monkeypatch):
    calls = {}
    monkeypatch.setattr(connectors.pyodbc, "drivers", lambda: ["ODBC Driver 18 for SQL Server"])

    class Column:
        name = "modified_id"
        primary_key = True
        type = connectors.Integer()

        def __gt__(self, value):
            calls["watermark_value"] = value
            return ("greater_than", value)

        def asc(self):
            return "ascending"

    class ColumnCollection:
        def __getitem__(self, name):
            if name == "modified_id":
                return Column()
            return name

    class FakeTable:
        c = ColumnCollection()
        constraints = set()
        primary_key = SimpleNamespace(columns=[Column()])
    class Statement:
        def where(self, clause):
            calls["where"] = clause
            return self

        def order_by(self, clause):
            calls["order_by"] = clause
            return self

        def limit(self, value):
            calls["limit"] = value
            return self

    class MappingResult:
        def yield_per(self, size):
            calls["yield_per"] = size
            return self

        def __iter__(self):
            return iter([{"modified_id": 11, "sku": "001"}])

    class ExecutionResult:
        def mappings(self):
            return MappingResult()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            return ExecutionResult()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            calls["disposed"] = True

    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", lambda *args, **kwargs: FakeTable())
    monkeypatch.setattr(connectors, "MetaData", lambda: object())
    monkeypatch.setattr(connectors, "select", lambda *columns: Statement())

    rows = fetch_sql_server_rows(
        "mssql+pyodbc://reader:secret@sql.example/catalog?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
        schema="dbo",
        table="Products",
        columns=["modified_id", "sku"],
        limit=100,
        watermark_column="modified_id",
        watermark_after="10",
    )
    assert rows == [{"modified_id": 11, "sku": "001"}]
    assert calls["watermark_value"] == 10
    assert calls["where"] == ("greater_than", 10)
    assert calls["order_by"] == "ascending"
    assert calls["limit"] == 101
    assert calls["disposed"] is True


def test_sql_server_requires_read_only_application_intent():
    with pytest.raises(SourceConnectorError, match="ApplicationIntent=ReadOnly"):
        fetch_sql_server_rows(
            "mssql+pyodbc://reader:secret@sql.example/catalog?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no",
            schema="dbo",
            table="Products",
            columns=["sku"],
        )



@pytest.mark.anyio
async def test_api_connector_rejects_full_page_when_only_one_page_is_allowed(monkeypatch):
    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            yield b'[{"sku":"001"}]'

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
    with pytest.raises(SourceConnectorError, match="configure a larger max_pages"):
        await fetch_api_records(
            "https://supplier.example/catalog",
            allowed_hosts={"supplier.example"},
            page_param="page",
            page_size_param="limit",
            page_size=1,
            max_pages=1,
        )



def test_sql_server_watermark_rejects_a_column_from_a_composite_primary_key(monkeypatch):
    metadata = MetaData()
    source_table = SQLTable(
        "Products",
        metadata,
        Column("tenant_id", Integer, primary_key=True),
        Column("modified_id", Integer, primary_key=True),
        Column("sku", String),
    )
    calls = {"executed": False, "disposed": False}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            calls["executed"] = True
            raise AssertionError("A non-unique watermark must be rejected before execution.")

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            calls["disposed"] = True

    monkeypatch.setattr(
        connectors.pyodbc, "drivers", lambda: ["ODBC Driver 18 for SQL Server"]
    )
    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", lambda *args, **kwargs: source_table)

    with pytest.raises(SourceConnectorError, match="unique or primary-key column"):
        fetch_sql_server_rows(
            "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
            schema="dbo",
            table="Products",
            columns=["tenant_id", "modified_id", "sku"],
            watermark_column="modified_id",
            watermark_after="10",
        )

    assert calls == {"executed": False, "disposed": True}


def test_sql_server_connector_rejects_potentially_truncated_row_limit(monkeypatch):
    calls = {"limit": None, "yielded": 0}

    class ColumnCollection:
        def __getitem__(self, name):
            return name

    class FakeTable:
        c = ColumnCollection()

    class Statement:
        def limit(self, value):
            calls["limit"] = value
            return self

    class MappingResult:
        def yield_per(self, size):
            return self

        def __iter__(self):
            for sku in ("001", "002"):
                calls["yielded"] += 1
                yield {"sku": sku}

    class ExecutionResult:
        def mappings(self):
            return MappingResult()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            return ExecutionResult()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(
        connectors.pyodbc, "drivers", lambda: ["ODBC Driver 18 for SQL Server"]
    )
    monkeypatch.setattr(connectors, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(connectors, "Table", lambda *args, **kwargs: FakeTable())
    monkeypatch.setattr(connectors, "MetaData", lambda: object())
    monkeypatch.setattr(connectors, "select", lambda *columns: Statement())

    with pytest.raises(SourceConnectorError, match="row limit"):
        fetch_sql_server_rows(
            "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&ApplicationIntent=ReadOnly",
            schema="dbo",
            table="Products",
            columns=["sku"],
            limit=1,
        )

    assert calls == {"limit": 2, "yielded": 2}


@pytest.mark.anyio
async def test_api_connector_converts_json_recursion_errors_to_safe_connector_errors(monkeypatch):
    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            yield b"{}"

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, *args, **kwargs):
            return Response()

    def reject_deep_json(*args, **kwargs):
        raise RecursionError("deeply nested JSON")

    monkeypatch.setattr(connectors, "_validate_https_url", lambda *args: None)
    monkeypatch.setattr(connectors.httpx, "AsyncClient", Client)
    monkeypatch.setattr(connectors.json, "loads", reject_deep_json)

    with pytest.raises(SourceConnectorError, match="nesting depth"):
        await fetch_api_records(
            "https://supplier.example/catalog",
            allowed_hosts={"supplier.example"},
        )
