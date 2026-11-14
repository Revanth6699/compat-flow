import pytest

from app.services.catalog_csv import CatalogCSVValidationError, parse_catalog_csv


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


def test_alias_headers_are_mapped_to_canonical_fields():
    content = (
        "product_sku,product_name,brand,mpn,product_category,warehouse_code\n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,W-01\n"
    )
    result = parse_catalog_csv(content)
    assert result.valid_count == 1
    assert {mapping.field: mapping.source_header for mapping in result.column_mappings} == {
        "sku": "product_sku",
        "name": "product_name",
        "manufacturer": "brand",
        "part_number": "mpn",
        "category": "product_category",
    }
    assert result.unmapped_headers == ["warehouse_code"]
    assert next(m.confidence for m in result.column_mappings if m.field == "manufacturer") == 0.88


def test_header_normalization_accepts_spaces_and_punctuation():
    content = (
        " Product SKU , Product Name , Manufacturer Name , Part No. , Category Name \n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes\n"
    )
    result = parse_catalog_csv(content)
    assert result.valid_count == 1


def test_ambiguous_aliases_are_rejected_instead_of_guessed():
    content = (
        "sku,product_sku,name,manufacturer,part_number,category\n"
        "SKU-1,SKU-2,Brake Pad,Maker A,BP-100,Brakes\n"
    )
    with pytest.raises(CatalogCSVValidationError, match="Ambiguous column mapping"):
        parse_catalog_csv(content)


def test_unknown_headers_are_reported_but_do_not_block_valid_catalog():
    content = (
        "sku,name,manufacturer,part_number,category,warehouse_code,region\n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,W-01,EU\n"
    )
    result = parse_catalog_csv(content)
    assert result.valid_count == 1
    assert result.unmapped_headers == ["warehouse_code", "region"]


def test_missing_required_mapping_returns_actionable_error():
    content = "sku,name,manufacturer,category\nSKU-1,Brake Pad,Maker A,Brakes\n"
    with pytest.raises(CatalogCSVValidationError, match="Could not map required product fields: part_number"):
        parse_catalog_csv(content)


def test_duplicate_headers_rejected_after_normalization():
    content = "sku, SKU ,name,manufacturer,part_number,category\n1,2,Name,Maker,P-1,Parts\n"
    with pytest.raises(CatalogCSVValidationError, match="duplicate column headers"):
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
    assert "Duplicate SKU" in result.errors[0]


def test_missing_required_value_rejected():
    result = parse_catalog_csv(VALID_HEADER + "SKU-1,,Maker A,BP-100,Brakes,,\n")
    assert result.valid_count == 0
    assert result.invalid_count == 1


def test_extra_column_in_row_rejected():
    result = parse_catalog_csv(VALID_HEADER + "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,EXTRA,UNEXPECTED\n")
    assert result.valid_count == 0
    assert result.invalid_count == 1
    assert "Expected" in result.errors[0]


def test_missing_value_column_in_row_rejected():
    result = parse_catalog_csv(VALID_HEADER + "SKU-1,Brake Pad,Maker A,BP-100,Brakes\n")
    assert result.valid_count == 0
    assert result.invalid_count == 1


def test_blank_lines_ignored():
    result = parse_catalog_csv(VALID_HEADER + "\nSKU-1,Brake Pad,Maker A,BP-100,Brakes,,\n\n")
    assert result.total_rows == 1
    assert result.valid_count == 1


def test_preview_limited_to_ten_rows():
    rows = "".join(f"SKU-{i},Product {i},Maker,PART-{i},Brakes,,\n" for i in range(15))
    result = parse_catalog_csv(VALID_HEADER + rows)
    assert result.total_rows == 15
    assert result.valid_count == 15
    assert len(result.preview) == 10


def test_malformed_csv_quoting_rejected():
    with pytest.raises(Exception):
        parse_catalog_csv(VALID_HEADER + 'SKU-1,"Unclosed product name,Maker A,BP-100,Brakes,,\n')


def test_structured_error_for_duplicate_sku():
    result = parse_catalog_csv(VALID_HEADER + (
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,\n"
        "SKU-1,Oil Filter,Maker A,OF-200,Filters,,\n"
    ))
    error = result.row_errors[0]
    assert error.row_number == 3
    assert error.field == "sku"
    assert error.error_code == "DUPLICATE_SKU_IN_FILE"


def test_structured_error_for_invalid_field():
    result = parse_catalog_csv(VALID_HEADER + "SKU-1,,Maker A,BP-100,Brakes,,\n")
    assert any(error.row_number == 2 and error.field == "name" for error in result.row_errors)


def test_structured_error_for_column_count_mismatch():
    result = parse_catalog_csv(VALID_HEADER + "SKU-1,Brake Pad,Maker A,BP-100,Brakes,EXTRA\n")
    error = result.row_errors[0]
    assert error.row_number == 2
    assert error.field is None
    assert error.error_code == "COLUMN_COUNT_MISMATCH"


def test_quality_score_uses_documented_formula():
    result = parse_catalog_csv(VALID_HEADER + "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,\n")
    assert result.validation_pass_rate == 100.0
    assert result.data_quality_score == 100.0



def test_manual_mapping_overrides_automatic_detection():
    content = "code,title,maker,mpn,type,unused\nSKU-1,Brake Pad,Maker A,BP-100,Brakes,x\n"
    mapping = {"sku": "code", "name": "title", "manufacturer": "maker", "part_number": "mpn", "category": "type"}
    result = parse_catalog_csv(content, column_mapping=mapping)
    assert result.valid_count == 1
    assert {item.field: item.source_header for item in result.column_mappings} == mapping
    assert result.unmapped_headers == ["unused"]


def test_manual_mapping_rejects_duplicate_source_columns():
    content = "code,title,maker,mpn,type\nSKU-1,Brake Pad,Maker A,BP-100,Brakes\n"
    mapping = {"sku": "code", "name": "code", "manufacturer": "maker", "part_number": "mpn", "category": "type"}
    with pytest.raises(CatalogCSVValidationError, match="source column cannot be mapped"):
        parse_catalog_csv(content, column_mapping=mapping)


def test_profile_requires_profile_specific_fields():
    content = "sku,name,manufacturer,part_number,category,replacement_sku\nSKU-1,Brake Pad,Maker A,BP-100,Brakes,\n"
    result = parse_catalog_csv(content, profile_id="electronics")
    assert result.valid_count == 0
    assert any(issue.error_code == "PROFILE_REQUIRED_FIELD_MISSING" and issue.field == "replacement_sku" for issue in result.row_errors)


def test_profile_rejects_unknown_profile():
    with pytest.raises(CatalogCSVValidationError, match="Unknown catalog profile"):
        parse_catalog_csv(VALID_HEADER, profile_id="unknown")


def test_metrics_separate_affected_records_from_issue_count():
    content = VALID_HEADER + "SKU-1,Brake Pad,Maker A,BP-100,Brakes,,\nSKU-1,Oil Filter,Maker A,OF-200,Filters,,\n"
    result = parse_catalog_csv(content)
    assert result.records_with_issues == 1
    assert result.duplicate_sku_count == 1
    assert result.duplicate_rate == 50.0
    assert result.issue_density == 0.5
    assert result.critical_record_rate == 50.0



def test_first_pass_preview_surfaces_ambiguous_aliases_for_manual_mapping():
    content = "sku,product_sku,name,manufacturer,part_number,category\nSKU-1,SKU-2,Brake Pad,Maker A,BP-100,Brakes\n"
    result = parse_catalog_csv(content, allow_incomplete_mapping=True)
    assert "sku" not in {mapping.field for mapping in result.column_mappings}
    assert "sku" in result.unmapped_headers
    assert "product_sku" in result.unmapped_headers



def test_semicolon_delimited_supplier_feed_is_detected():
    content = (
        "product_code;name;price_gross;vat;currency;stock\n"
        "SKU-1;Electric guitar;129.99;21;EUR;4\n"
    )
    result = parse_catalog_csv(
        content,
        column_mapping={"sku": "product_code", "name": "name"},
        allow_incomplete_mapping=True,
    )
    assert result.total_rows == 1
    assert result.valid_count == 0
    assert {item.field: item.source_header for item in result.column_mappings} == {
        "sku": "product_code",
        "name": "name",
    }
    assert result.unmapped_headers == ["price_gross", "vat", "currency", "stock"]


def test_tab_delimited_feed_is_detected():
    content = (
        "sku\tname\tmanufacturer\tpart_number\tcategory\n"
        "SKU-1\tBrake Pad\tMaker A\tBP-100\tBrakes\n"
    )
    result = parse_catalog_csv(content)
    assert result.total_rows == 1
    assert result.valid_count == 1


def test_pipe_delimited_feed_is_detected():
    content = (
        "sku|name|manufacturer|part_number|category\n"
        "SKU-1|Brake Pad|Maker A|BP-100|Brakes\n"
    )
    result = parse_catalog_csv(content)
    assert result.total_rows == 1
    assert result.valid_count == 1
