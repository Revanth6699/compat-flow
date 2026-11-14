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


def test_xml_single_record_root_is_not_split_into_field_records():
    parsed = parse_xml(b'<Product><SKU>001</SKU><Name>Widget</Name></Product>')
    assert len(parsed.records) == 1
    assert parsed.records[0].values == {"SKU": "001", "Name": "Widget"}


def test_xml_multiple_repeated_groups_require_explicit_record_tag():
    with pytest.raises(IngestionParseError, match="multiple repeated record groups"):
        parse_xml(b'<feed><products><product><sku>A</sku></product><product><sku>B</sku></product></products><variants><variant><code>A</code></variant><variant><code>B</code></variant></variants></feed>')


def test_xml_single_record_inside_collection_wrapper():
    parsed = parse_xml(b'<Products><Product><SKU>001</SKU><Name>Widget</Name></Product></Products>')
    assert len(parsed.records) == 1
    assert parsed.records[0].values == {"SKU": "001", "Name": "Widget"}


def test_csv_rejects_non_utf8_and_record_limit():
    with pytest.raises(IngestionParseError, match="UTF-8"):
        parse_csv(b"\\xff\\xfe")
    with pytest.raises(IngestionParseError, match="record limit"):
        parse_csv(b"sku\\nA\\nB\\n", max_records=1)


def test_csv_rejects_empty_headers_and_duplicate_headers():
    with pytest.raises(IngestionParseError, match="empty or missing header"):
        parse_csv(b"sku,,name\\n1,2,3\\n")
    with pytest.raises(IngestionParseError, match="Duplicate headers"):
        parse_csv(b"sku,SKU\\n1,2\\n")


def test_json_rejects_malformed_payload_and_missing_record_path():
    with pytest.raises(IngestionParseError, match="valid UTF-8 JSON"):
        parse_json(b"{not-json}")
    with pytest.raises(IngestionParseError, match="record path does not exist"):
        parse_json(b'{"data": []}', record_path="missing.items")


def test_json_enforces_record_and_cell_limits():
    with pytest.raises(IngestionParseError, match="record limit"):
        parse_json(b'[{"sku":"A"},{"sku":"B"}]', max_records=1)
    with pytest.raises(IngestionParseError, match="maximum cell size"):
        parse_json(('{"sku":"' + ("x" * 20) + '"}').encode(), max_records=1)


def test_excel_rejects_missing_sheet_and_invalid_header_row():
    openpyxl = pytest.importorskip("openpyxl")
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    workbook.active.append(["sku", "name"])
    workbook.save(output)
    with pytest.raises(IngestionParseError, match="worksheet does not exist"):
        parse_excel(output.getvalue(), ".xlsx", sheet_name="Missing")
    with pytest.raises(IngestionParseError, match="header_row"):
        parse_excel(output.getvalue(), ".xlsx", header_row=0)


def test_parse_source_dispatches_xml_and_rejects_missing_extension():
    parsed = parse_source(b"<Products><Product><sku>A</sku></Product></Products>", "feed.XML")
    assert parsed.format == "xml"
    with pytest.raises(IngestionParseError, match="extension is required"):
        parse_source(b"sku,name", "catalog")
