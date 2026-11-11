
import pytest

from app.services.catalog_csv import (
    CatalogCSVValidationError,
    parse_catalog_csv,
)


VALID_HEADER = (
    "sku,name,manufacturer,part_number,category,"
    "compatibility,replacement_sku\n"
)


def test_valid_csv():
    content = VALID_HEADER + (
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,VEH-001,\n"
        "SKU-2,Oil Filter,Maker B,OF-200,Filters,ENGINE-001,\n"
    )

    result = parse_catalog_csv(content)

    assert result.total_rows == 2
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert len(result.preview) == 2


def test_duplicate_headers_rejected():
    content = (
        "sku,name,SKU,manufacturer,part_number,category\n"
        "1,Brake Pad,2,Maker A,BP-100,Brakes\n"
    )

    with pytest.raises(CatalogCSVValidationError, match="duplicate"):
        parse_catalog_csv(content)


def test_missing_required_column_rejected():
    content = "sku,name,manufacturer,part_number\n"

    with pytest.raises(CatalogCSVValidationError, match="Missing required"):
        parse_catalog_csv(content)


def test_duplicate_sku_rejected_from_valid_records():
    content = VALID_HEADER + (
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,\n"
        "SKU-1,Oil Filter,Maker A,OF-200,Filters,,\n"
    )

    result = parse_catalog_csv(content)

    assert result.total_rows == 2
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert "duplicate SKU" in result.errors[0]


def test_missing_required_value_rejected():
    content = VALID_HEADER + (
        "SKU-1,,Maker A,BP-100,Brakes,,\n"
    )

    result = parse_catalog_csv(content)

    assert result.valid_count == 0
    assert result.invalid_count == 1


def test_extra_column_in_row_rejected():
    content = VALID_HEADER + (
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,EXTRA,UNEXPECTED\n"
    )

    result = parse_catalog_csv(content)

    assert result.valid_count == 0
    assert result.invalid_count == 1
    assert "expected" in result.errors[0]

def test_missing_value_column_in_row_rejected():
    content = VALID_HEADER + (
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes\n"
    )

    result = parse_catalog_csv(content)

    assert result.valid_count == 0
    assert result.invalid_count == 1


def test_header_whitespace_and_case_normalized():
    content = (
        " SKU , NAME , MANUFACTURER , PART_NUMBER , CATEGORY \n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes\n"
    )

    result = parse_catalog_csv(content)

    assert result.valid_count == 1


def test_blank_lines_ignored():
    content = VALID_HEADER + (
        "\n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,\n"
        "\n"
    )

    result = parse_catalog_csv(content)

    assert result.total_rows == 1
    assert result.valid_count == 1


def test_preview_limited_to_ten_rows():
    rows = "".join(
        f"SKU-{i},Product {i},Maker,PART-{i},Brakes,,\n"
        for i in range(15)
    )

    result = parse_catalog_csv(VALID_HEADER + rows)

    assert result.total_rows == 15
    assert result.valid_count == 15
    assert len(result.preview) == 10


def test_malformed_csv_quoting_rejected():
    content = VALID_HEADER + (
        'SKU-1,"Unclosed product name,Maker A,BP-100,Brakes,,\n'
    )

    with pytest.raises(Exception):
        parse_catalog_csv(content)
