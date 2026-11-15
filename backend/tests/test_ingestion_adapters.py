import io
import json
import zipfile

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
        parse_csv(b"\xff\xfe")
    with pytest.raises(IngestionParseError, match="record limit"):
        parse_csv(b"sku\nA\nB\n", max_records=1)


def test_csv_rejects_empty_headers_and_duplicate_headers():
    with pytest.raises(IngestionParseError, match="empty or missing header"):
        parse_csv(b"sku,,name\n1,2,3\n")
    with pytest.raises(IngestionParseError, match="Duplicate headers"):
        parse_csv(b"sku,SKU\n1,2\n")


def test_json_rejects_malformed_payload_and_missing_record_path():
    with pytest.raises(IngestionParseError, match="valid UTF-8 JSON"):
        parse_json(b"{not-json}")
    with pytest.raises(IngestionParseError, match="record path does not exist"):
        parse_json(b'{"data": []}', record_path="missing.items")


def test_json_enforces_record_and_cell_limits(monkeypatch):
    with pytest.raises(IngestionParseError, match="record limit"):
        parse_json(b'[{"sku":"A"},{"sku":"B"}]', max_records=1)
    monkeypatch.setattr("app.services.ingestion_adapters.MAX_CELL_CHARS", 10)
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



def test_xlsx_rejects_excessive_uncompressed_archive_size(monkeypatch):
    openpyxl = pytest.importorskip("openpyxl")
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    workbook.active.append(["sku", "name"])
    workbook.active.append(["001", "Widget"])
    workbook.save(output)
    output.seek(0)
    with zipfile.ZipFile(output, "a", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("xl/uncompressed-overflow.bin", b"x" * 200)
    monkeypatch.setattr(
        "app.services.ingestion_adapters.MAX_XLSX_UNCOMPRESSED_BYTES", 100
    )
    with pytest.raises(IngestionParseError, match="uncompressed size limit"):
        parse_excel(output.getvalue(), ".xlsx")


def test_xlsx_trims_trailing_empty_header_cells():
    openpyxl = pytest.importorskip("openpyxl")
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["sku", "name", None, ""])
    sheet.append(["001", "Widget", None, ""])
    workbook.save(output)
    parsed = parse_excel(output.getvalue(), ".xlsx")
    assert parsed.headers == ["sku", "name"]
    assert parsed.records[0].values == {"sku": "001", "name": "Widget"}


def test_json_rejects_duplicate_flattened_paths():
    with pytest.raises(IngestionParseError, match="duplicate flattened field paths"):
        parse_json(b'{"a":{"b":"nested"},"a.b":"flat"}')


def test_xml_rejects_repeated_nested_child_values():
    payload = (
        b"<Records><Record><attributes><color>red</color>"
        b"<color>blue</color></attributes></Record></Records>"
    )
    with pytest.raises(IngestionParseError, match="repeated nested field"):
        parse_xml(payload)


def test_parse_source_rejects_input_over_source_byte_limit(monkeypatch):
    monkeypatch.setattr("app.services.ingestion_adapters.MAX_SOURCE_BYTES", 4)
    with pytest.raises(IngestionParseError, match="maximum source byte limit"):
        parse_source(b"12345", "catalog.csv")



def test_excel_rejects_extreme_header_row_and_physical_sheet_dimensions():
    openpyxl = pytest.importorskip("openpyxl")
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["sku", "name"])
    sheet.append(["001", "Widget"])
    sheet["A20"] = "outside-bound"
    workbook.save(output)
    with pytest.raises(IngestionParseError, match="header_row"):
        parse_excel(output.getvalue(), ".xlsx", header_row=1001)
    with pytest.raises(IngestionParseError, match="dimensions"):
        parse_excel(output.getvalue(), ".xlsx", max_records=10)


def test_json_rejects_excessive_nesting_without_leaking_recursion_error():
    payload = ("[" * 1200 + "{}" + "]" * 1200).encode()
    with pytest.raises(IngestionParseError):
        parse_json(payload)


def test_xml_rejects_nested_fields_deeper_than_supported():
    payload = (
        b"<Records><Record><details><manufacturer><name>Acme</name>"
        b"</manufacturer></details></Record></Records>"
    )
    with pytest.raises(IngestionParseError, match="supported nesting depth"):
        parse_xml(payload)


def _assert_industry_pipeline(parsed):
    from app.services.industry_catalog import validate_industry_records

    result = validate_industry_records(
        parsed.headers, [record.values for record in parsed.records], profile_id="ecommerce"
    )
    assert result["total_rows"] == 2
    assert result["valid_rows"] == 2
    assert result["invalid_rows"] == 0
    assert {item["field"] for item in result["column_mappings"]} >= {
        "sku", "title", "unit_price", "currency"
    }
    assert result["preview"][0]["currency"] == "USD"
    assert result["persisted"] is False


def test_csv_and_json_feed_the_same_industry_pipeline():
    csv_source = parse_source(
        b"sku,title,price,currency\nS-1,Widget,12.50,USD\nS-2,Gadget,8,EUR\n",
        "catalog.csv",
    )
    json_source = parse_source(
        b'[{"sku":"S-1","title":"Widget","price":12.5,"currency":"USD"},'
        b'{"sku":"S-2","title":"Gadget","price":8,"currency":"EUR"}]',
        "catalog.json",
    )
    _assert_industry_pipeline(csv_source)
    _assert_industry_pipeline(json_source)


def test_xlsx_feeds_the_same_industry_pipeline():
    openpyxl = pytest.importorskip("openpyxl")
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Catalog"
    sheet.append(["sku", "title", "price", "currency"])
    sheet.append(["S-1", "Widget", 12.5, "USD"])
    sheet.append(["S-2", "Gadget", 8, "EUR"])
    workbook.save(output)

    parsed = parse_source(output.getvalue(), "catalog.xlsx")
    assert parsed.metadata["sheet"] == "Catalog"
    _assert_industry_pipeline(parsed)


def test_xls_feeds_the_same_industry_pipeline(monkeypatch):
    import sys
    import types

    class Sheet:
        name = "Catalog"
        nrows = 3

        def row_values(self, index):
            return [
                ["sku", "title", "price", "currency"],
                ["S-1", "Widget", 12.5, "USD"],
                ["S-2", "Gadget", 8, "EUR"],
            ][index]

    class Workbook:
        def sheet_by_index(self, index):
            assert index == 0
            return Sheet()

        def release_resources(self):
            pass

    monkeypatch.setitem(
        sys.modules,
        "xlrd",
        types.SimpleNamespace(
            open_workbook=lambda **kwargs: Workbook(),
            XLRDError=type("XLRDError", (Exception,), {}),
        ),
    )
    parsed = parse_source(b"mock-xls-bytes", "catalog.xls")
    assert parsed.metadata["sheet"] == "Catalog"
    _assert_industry_pipeline(parsed)


def test_xml_feeds_the_same_industry_pipeline():
    parsed = parse_source(
        b"<products>"
        b"<product><sku>S-1</sku><title>Widget</title><price>12.5</price><currency>USD</currency></product>"
        b"<product><sku>S-2</sku><title>Gadget</title><price>8</price><currency>EUR</currency></product>"
        b"</products>",
        "catalog.xml",
    )
    _assert_industry_pipeline(parsed)

# CI regression coverage for the format-neutral industry ingestion path.
