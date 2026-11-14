import io
import json

import pytest

from app.services.ingestion_adapters import (
    IngestionParseError,
    parse_csv,
    parse_excel,
    parse_json,
    parse_source,
    parse_xml,
)


def test_csv_adapter_preserves_source_row_and_delimiter():
    parsed = parse_csv(b"SKU;Name\n001;Widget\n")
    assert parsed.format == "csv"
    assert parsed.metadata["delimiter"] == ";"
    assert parsed.records[0].values["SKU"] == "001"
    assert parsed.records[0].source_location == "row:2"


def test_json_adapter_flattens_nested_objects_without_losing_path():
    parsed = parse_json(json.dumps([{"id": 7, "product": {"sku": "001"}}]).encode())
    assert parsed.records[0].values["product.sku"] == "001"
    assert parsed.records[0].source_key == "7"


def test_json_adapter_requires_record_path_for_ambiguous_nested_lists():
    with pytest.raises(IngestionParseError, match="record_path"):
        parse_json(b'{"products":[{"sku":"A"}],"variants":[{"sku":"B"}]}')


def test_xml_adapter_supports_namespaces_and_repeated_records():
    parsed = parse_xml(
        b'<feed xmlns="urn:test"><item id="A"><sku>001</sku></item>'
        b'<item id="B"><sku>002</sku></item></feed>'
    )
    assert len(parsed.records) == 2
    assert parsed.records[0].values["sku"] == "001"
    assert parsed.records[0].source_key == "A"


def test_xml_rejects_unsafe_or_malformed_payload():
    with pytest.raises(IngestionParseError):
        parse_xml(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>')


def test_duplicate_csv_headers_are_rejected():
    with pytest.raises(IngestionParseError, match="Duplicate headers"):
        parse_csv(b"SKU, sku\n1,2\n")


def test_unsupported_file_extension_is_rejected():
    with pytest.raises(IngestionParseError, match="Unsupported file type"):
        parse_source(b"data", "catalog.pdf")


def test_excel_xlsx_adapter_reads_selected_sheet():
    openpyxl = pytest.importorskip("openpyxl")
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(["SKU", "Name"])
    sheet.append(["001", "Widget"])
    workbook.save(output)
    parsed = parse_excel(output.getvalue(), ".xlsx", sheet_name="Products")
    assert parsed.records[0].values["SKU"] == "001"
    assert parsed.records[0].source_location == "sheet:Products!row:2"
