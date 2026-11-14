import pytest

from app.services.source_connectors import (
    SourceConnectorError,
    _validate_https_url,
    fetch_sql_server_rows,
)


def test_api_connector_requires_https_and_allowlisted_host():
    _validate_https_url("https://supplier.example/api", {"supplier.example"})
    with pytest.raises(SourceConnectorError, match="HTTPS"):
        _validate_https_url("http://supplier.example/api", {"supplier.example"})
    with pytest.raises(SourceConnectorError, match="allowlist"):
        _validate_https_url("https://other.example/api", {"supplier.example"})


def test_api_connector_rejects_embedded_credentials():
    with pytest.raises(SourceConnectorError):
        _validate_https_url("https://user:password@supplier.example/api", {"supplier.example"})


def test_sql_server_connector_rejects_non_sql_server_urls():
    with pytest.raises(SourceConnectorError, match="mssql"):
        fetch_sql_server_rows("postgresql://example/db", schema="dbo",
                              table="Products", columns=["sku"])


@pytest.mark.parametrize("identifier", ["Products; DROP TABLE Users", "dbo.Products", "bad-name"])
def test_sql_server_connector_rejects_unsafe_table_identifiers(identifier):
    with pytest.raises(SourceConnectorError, match="identifier"):
        fetch_sql_server_rows("mssql+pyodbc://user:pass@host/db", schema="dbo",
                              table=identifier, columns=["sku"])
