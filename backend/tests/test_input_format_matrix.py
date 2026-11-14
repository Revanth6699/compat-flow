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


def test_spreadsheet_formats_report_missing_required_product_fields():
    invalid = {
        "sku": "001",
        "name": "",
        "manufacturer": "Acme",
        "part_number": "A-1",
        "category": "Parts",
    }

    xlsx_output = io.BytesIO()
    xlsx_workbook = openpyxl.Workbook()
    xlsx_sheet = xlsx_workbook.active
    xlsx_sheet.append(list(invalid))
    xlsx_sheet.append(list(invalid.values()))
    xlsx_workbook.save(xlsx_output)

    xls_output = io.BytesIO()
    xls_workbook = xlwt.Workbook()
    xls_sheet = xls_workbook.add_sheet("Products")
    for column, value in enumerate(invalid):
        xls_sheet.write(0, column, value)
    for column, value in enumerate(invalid.values()):
        xls_sheet.write(1, column, value)
    xls_workbook.save(xls_output)

    for filename, payload in [
        ("bad.xlsx", xlsx_output.getvalue()),
        ("bad.xls", xls_output.getvalue()),
    ]:
        parsed = parse_source(payload, filename)
        result = validate_parsed_records(parsed, "products")
        assert result.total_records == 1, filename
        assert result.invalid_records == 1, filename
        assert any(error["field"] == "name" for error in result.errors), filename


RECORD_CASES = {
    "products": {
        "sku": "001", "name": "Widget", "manufacturer": "Acme",
        "part_number": "A-1", "category": "Parts",
    },
    "product_variants": {
        "product_id": "00000000-0000-0000-0000-000000000001",
        "variant_sku": "VAR-001", "attributes": '{"color":"blue"}',
    },
    "supplier_offers": {
        "supplier_id": "00000000-0000-0000-0000-000000000002",
        "supplier_sku": "SUP-001", "unit_price": "12.50", "currency": "USD",
    },
    "inventory_snapshots": {
        "product_id": "00000000-0000-0000-0000-000000000001",
        "warehouse_code": "WH-01", "quantity_on_hand": "25",
    },
    "product_identifiers": {
        "product_id": "00000000-0000-0000-0000-000000000001",
        "identifier_type": "gtin", "value": "00012345678905",
    },
}


def _serialize_record(filename, record):
    extension = filename.rsplit(".", 1)[1]
    if extension == "csv":
        import csv
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(record))
        writer.writeheader()
        writer.writerow(record)
        return output.getvalue().encode()
    if extension == "json":
        return json.dumps([record]).encode()
    if extension == "xml":
        fields = "".join(f"<{key}>{value}</{key}>" for key, value in record.items())
        return f"<Records><Record>{fields}</Record></Records>".encode()
    if extension == "xlsx":
        output = io.BytesIO()
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(list(record))
        sheet.append(list(record.values()))
        workbook.save(output)
        return output.getvalue()
    if extension == "xls":
        output = io.BytesIO()
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("Records")
        for column, value in enumerate(record):
            sheet.write(0, column, value)
        for column, value in enumerate(record.values()):
            sheet.write(1, column, value)
        workbook.save(output)
        return output.getvalue()
    raise AssertionError(f"Unsupported fixture extension: {extension}")


def test_all_five_catalog_record_types_validate_across_all_supported_formats():
    formats = ("csv", "json", "xml", "xlsx", "xls")
    for record_type, record in RECORD_CASES.items():
        for extension in formats:
            filename = f"{record_type}.{extension}"
            payload = _serialize_record(filename, record)
            parsed = parse_source(payload, filename)
            result = validate_parsed_records(parsed, record_type)
            assert result.total_records == 1, (record_type, extension)
            assert result.invalid_records == 0, (record_type, extension, result.errors)
            assert len(result.valid_records) == 1, (record_type, extension)
