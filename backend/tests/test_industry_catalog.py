import pytest

from app.services.industry_catalog import (
    IndustryCSVError,
    detect_industry,
    validate_industry_csv,
    validate_industry_records,
)


def mapped(result):
    return {item["field"]: item["source_header"] for item in result["column_mappings"]}


def test_olist_product_export_maps_source_id_and_measurements_without_inventing_sku():
    content = (
        "product_id,product_category_name,product_name_lenght,"
        "product_description_lenght,product_photos_qty,product_weight_g,"
        "product_length_cm,product_height_cm,product_width_cm\n"
        "0001,beleza,40,200,3,500,20,10,15\n"
    )
    result = validate_industry_csv(content, profile_id="ecommerce")
    fields = mapped(result)
    assert fields["source_product_id"] == "product_id"
    assert fields["category"] == "product_category_name"
    assert fields["name_length"] == "product_name_lenght"
    assert fields["description_length"] == "product_description_lenght"
    assert fields["image_count"] == "product_photos_qty"
    assert fields["weight_g"] == "product_weight_g"
    assert "sku" not in fields
    assert "manufacturer" not in fields
    assert result["preview"][0]["source_product_id"] == "0001"


@pytest.mark.parametrize(
    ("profile", "header", "row", "expected"),
    [
        ("d2c", "title,brand,size,colour,material,parent_product_id,variant_id",
         "Cotton Tee,Acme,M,Blue,Cotton,P-1,V-1", {"title", "brand", "size", "colour", "material"}),
        ("ecommerce", "sku,title,gtin,category,price,currency,stock",
         "S-1,Phone,0123456789012,Electronics,99.00,USD,4", {"sku", "title", "gtin", "category", "unit_price", "currency", "quantity"}),
        ("automotive", "manufacturer,mpn,year,make,vehicle_model,engine,position",
         "Maker,BP-1,2020,Ford,Focus,2.0,Front", {"manufacturer", "mpn", "year", "make", "vehicle_model", "engine", "position"}),
        ("electronics", "manufacturer,mpn,model_number,voltage,wattage,frequency",
         "Maker,ABC-1,Model X,12,60,50", {"manufacturer", "mpn", "model_number", "voltage", "power_w", "frequency_hz"}),
        ("industrial", "manufacturer,mpn,material,diameter,pressure_rating,standard",
         "Maker,VALVE-1,Steel,10,16,ISO", {"manufacturer", "mpn", "material", "diameter", "pressure_rating", "standard"}),
        ("wholesale", "supplier_id,supplier_sku,buyer_sku,price,currency,moq,order_multiple,uom,lead_time_days",
         "SUP-1,V-1,B-1,4.50,EUR,10,5,EA,7", {"supplier_id", "supplier_sku", "buyer_sku", "unit_price", "currency", "moq", "order_multiple", "unit_of_measure", "lead_time_days"}),
    ],
)
def test_all_six_profiles_map_industry_fields(profile, header, row, expected):
    result = validate_industry_csv(header + "\n" + row + "\n", profile_id=profile)
    assert expected.issubset(set(mapped(result)))
    assert result["total_rows"] == 1


def test_ambiguous_profile_detection_does_not_force_choice():
    result = detect_industry(["id", "name", "description", "created_at"])
    assert result["profile_id"] is None
    assert result["needs_confirmation"] is True


def test_invalid_numeric_values_are_reported_not_raised():
    result = validate_industry_csv(
        "sku,title,price,currency\nS-1,Widget,not-a-price,USD\n",
        profile_id="ecommerce",
    )
    assert any(issue["error_code"] == "INVALID_NONNEGATIVE_NUMBER" for issue in result["issues"])


def test_price_requires_currency():
    result = validate_industry_csv(
        "sku,title,price\nS-1,Widget,12.50\n",
        profile_id="ecommerce",
    )
    assert any(issue["error_code"] == "PRICE_CURRENCY_MISSING" for issue in result["issues"])


def test_wholesale_supplier_sku_duplicate_is_scoped_by_supplier():
    result = validate_industry_csv(
        "supplier_id,supplier_sku\nSUP-A,X1\nSUP-B,X1\nSUP-A,X1\n",
        profile_id="wholesale",
    )
    duplicates = [i for i in result["issues"] if i["error_code"] == "DUPLICATE_IDENTIFIER"]
    assert len(duplicates) == 1
    assert duplicates[0]["row_number"] == 4


def test_unknown_profile_rejected():
    with pytest.raises(IndustryCSVError, match="Unknown industry profile"):
        validate_industry_csv("sku,title\nS-1,Widget\n", profile_id="pharma")


def test_format_neutral_adapter_applies_same_industry_mapping_to_extracted_records():
    headers = ["sku", "title", "price", "currency"]
    records = [
        {"sku": "S-1", "title": "Widget", "price": 12.5, "currency": "usd"},
        {"sku": "S-2", "title": "Gadget", "price": 8, "currency": "EUR"},
    ]
    result = validate_industry_records(headers, records, profile_id="ecommerce")
    assert result["total_rows"] == 2
    assert result["valid_rows"] == 2
    assert mapped(result)["unit_price"] == "price"
    assert result["preview"][0]["currency"] == "USD"


def test_inventory_available_quantity_alias_is_distinct_and_checked():
    result = validate_industry_csv(
        "sku,title,quantity_on_hand,quantity_reserved,quantity_available\n"
        "S-1,Widget,10,3,9\n",
        profile_id="ecommerce",
    )
    assert mapped(result)["quantity_available"] == "quantity_available"
    assert any(issue["error_code"] == "INVENTORY_QUANTITY_MISMATCH" for issue in result["issues"])


def test_demo_industry_adapter_accepts_more_than_ten_thousand_rows():
    headers = ["product_id", "product_category_name", "product_weight_g"]
    records = [
        {"product_id": f"p-{index}", "product_category_name": "beleza", "product_weight_g": 100}
        for index in range(10_001)
    ]
    result = validate_industry_records(headers, records, profile_id="ecommerce", max_rows=None)
    assert result["total_rows"] == 10_001
