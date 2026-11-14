import io
import json

import openpyxl
import xlwt

from app.services.ingestion_adapters import parse_source
from app.services.record_import import validate_parsed_records


PRODUCT = {
    "sku": "001",
    "name": "Widget",
    "manufacturer": "Acme",
    "part_number": "A-1",
    "category": "Parts",
}


def _xlsx_bytes():
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(list(PRODUCT))
    sheet.append(list(PRODUCT.values()))
    workbook.save(output)
    return output.getvalue()


def _xls_bytes():
    output = io.BytesIO()
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Products")
    for column, value in enumerate(PRODUCT):
        sheet.write(0, column, value)
    for column, value in enumerate(PRODUCT.values()):
        sheet.write(1, column, value)
    workbook.save(output)
    return output.getvalue()


def _input_cases():
    headers = ",".join(PRODUCT)
    values = ",".join(PRODUCT.values())
    xml = (
        "<Products><Product>"
        + "".join(f"<{key}>{value}</{key}>" for key, value in PRODUCT.items())
        + "</Product></Products>"
    )
    return [
        ("catalog.csv", f"{headers}\n{values}\n".encode()),
        ("catalog.json", json.dumps([PRODUCT]).encode()),
        ("catalog.xml", xml.encode()),
        ("catalog.xlsx", _xlsx_bytes()),
        ("catalog.xls", _xls_bytes()),
    ]


def test_every_supported_file_format_reaches_product_validation():
    for filename, payload in _input_cases():
        parsed = parse_source(payload, filename)
        result = validate_parsed_records(parsed, "products")
        assert parsed.records, filename
        assert result.total_records == 1, filename
        assert len(result.valid_records) == 1, (filename, result.errors)
        assert result.invalid_records == 0, filename
        assert result.valid_records[0]["sku"] == "001", filename


def test_xls_sheet_selection_and_source_location_are_preserved():
    parsed = parse_source(_xls_bytes(), "catalog.xls", sheet_name="Products")
    assert parsed.format == "xls"
    assert parsed.metadata["sheet"] == "Products"
    assert parsed.records[0].source_location == "sheet:Products!row:2"
    assert parsed.records[0].values["sku"] == "001"


def test_supported_text_formats_reject_invalid_product_rows_consistently():
    invalid = {
        "sku": "001",
        "name": "",
        "manufacturer": "Acme",
        "part_number": "A-1",
        "category": "Parts",
    }
    xml = (
        "<Products><Product>"
        + "".join(f"<{key}>{value}</{key}>" for key, value in invalid.items())
        + "</Product></Products>"
    )
    cases = [
        ("bad.csv", (",".join(invalid) + "\n" + ",".join(invalid.values()) + "\n").encode()),
        ("bad.json", json.dumps([invalid]).encode()),
        ("bad.xml", xml.encode()),
    ]
    for filename, payload in cases:
        parsed = parse_source(payload, filename)
        result = validate_parsed_records(parsed, "products")
        assert result.total_records == 1, filename
        assert result.invalid_records == 1, filename
        assert any(error["field"] == "name" for error in result.errors), filename
