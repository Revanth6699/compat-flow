import pytest

from app.services.ingestion_adapters import parse_json
from app.services.record_import import RecordMappingError, validate_parsed_records


def test_validate_product_records_with_exact_header_mapping():
    parsed = parse_json(b'[{"sku":"001","name":"Widget","manufacturer":"Acme","part_number":"A-1","category":"Parts"}]')
    result = validate_parsed_records(parsed, "products")
    assert result.total_records == 1
    assert len(result.valid_records) == 1
    assert result.invalid_records == 0


def test_validate_variant_records_and_nested_attributes():
    parsed = parse_json(b'[{"product_id":"00000000-0000-0000-0000-000000000001","variant_sku":"V-1","attributes":{"color":"red"}}]')
    result = validate_parsed_records(parsed, "product_variants")
    assert result.valid_records[0]["attributes"] == {"color": "red"}


def test_validate_supplier_offer_records():
    parsed = parse_json(b'[{"supplier_id":"00000000-0000-0000-0000-000000000002","supplier_sku":"S-1","unit_price":"12.50","currency":"USD"}]')
    result = validate_parsed_records(parsed, "supplier_offers")
    assert result.valid_records[0]["unit_price"] == "12.5000"


def test_validate_inventory_snapshot_records():
    parsed = parse_json(b'[{"product_id":"00000000-0000-0000-0000-000000000001","warehouse_code":"W1","quantity_on_hand":"4"}]')
    result = validate_parsed_records(parsed, "inventory_snapshots")
    assert result.valid_records[0]["quantity_on_hand"] == "4.0000"


def test_validate_product_identifier_records_and_duplicate_detection():
    parsed = parse_json(b'[{"product_id":"00000000-0000-0000-0000-000000000001","identifier_type":"gtin","value":"000123"},{"product_id":"00000000-0000-0000-0000-000000000001","identifier_type":"gtin","value":"000123"}]')
    result = validate_parsed_records(parsed, "product_identifiers")
    assert len(result.valid_records) == 1
    assert result.errors[0]["error_code"] == "DUPLICATE_IN_FILE"


def test_missing_required_mappings_are_reported_as_row_validation_errors():
    parsed = parse_json(b'[{"sku":"001","name":"Widget"}]')
    result = validate_parsed_records(parsed, "products")
    assert result.invalid_records == 1
    assert any(error["field"] == "manufacturer" for error in result.errors)


def test_manual_mapping_is_record_type_scoped():
    parsed = parse_json(b'[{"item_ref":"001","title":"Widget","maker":"Acme","mpn":"A-1","type":"Parts"}]')
    mapping = {
        "sku": "item_ref",
        "name": "title",
        "manufacturer": "maker",
        "part_number": "mpn",
        "category": "type",
    }
    result = validate_parsed_records(parsed, "products", mapping)
    assert len(result.valid_records) == 1
    assert result.mappings[0]["confidence"] == 1.0
