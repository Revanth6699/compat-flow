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


def test_gtin_check_digit_is_validated():
    valid = validate_industry_csv("sku,title,gtin\nS-1,Widget,4006381333931\n", profile_id="ecommerce")
    invalid = validate_industry_csv("sku,title,gtin\nS-1,Widget,4006381333932\n", profile_id="ecommerce")
    assert not any(i["error_code"] == "INVALID_GTIN_CHECK_DIGIT" for i in valid["issues"])
    assert any(i["error_code"] == "INVALID_GTIN_CHECK_DIGIT" for i in invalid["issues"])


def test_urls_must_be_absolute_http_or_https():
    result = validate_industry_csv("title,product_url\nWidget,ftp://example.com/item\n", profile_id="d2c")
    assert any(i["error_code"] == "INVALID_HTTP_URL" for i in result["issues"])


def test_reserved_inventory_cannot_exceed_on_hand():
    result = validate_industry_csv("sku,title,quantity_on_hand,quantity_reserved\nS-1,Widget,5,8\n", profile_id="ecommerce")
    assert any(i["error_code"] == "RESERVED_EXCEEDS_ON_HAND" for i in result["issues"])


def test_declared_product_name_length_is_compared_with_actual_text():
    result = validate_industry_csv("title,product_name_length\nWidget,99\n", profile_id="d2c")
    assert any(i["error_code"] == "TEXT_LENGTH_MISMATCH" for i in result["issues"])
    assert result["valid_rows"] == 1


def test_invalid_date_range_is_reported():
    result = validate_industry_csv("title,effective_date,expiry_date\nWidget,2025-05-01,2025-04-01\n", profile_id="d2c")
    assert any(i["error_code"] == "DATE_RANGE_INVALID" for i in result["issues"])


def test_measurements_must_be_positive_and_counts_whole_numbers():
    result = validate_industry_csv("title,weight_g,image_count\nWidget,0,1.5\n", profile_id="d2c")
    codes = {i["error_code"] for i in result["issues"]}
    assert "MEASUREMENT_MUST_BE_POSITIVE" in codes
    assert "INTEGER_VALUE_REQUIRED" in codes


def test_malformed_datetime_is_not_accepted_as_valid_date():
    result = validate_industry_csv("title,effective_date\nWidget,2025-01-01Tnot-a-time\n", profile_id="d2c")
    assert any(i["error_code"] == "INVALID_DATE_VALUE" for i in result["issues"])


def test_zepto_marketplace_fields_map_and_validate_without_conflating_quantity_and_stock():
    result = validate_industry_csv(
        "category,title,quantity,mrp,discountPercent,availableQuantity,"
        "discountedSellingPrice,weightInGms,outOfStock,currency\n"
        "Snacks,Chips,6,100,20,0,80,250,true,INR\n",
        profile_id="ecommerce",
    )
    fields = mapped(result)
    assert fields["category"] == "category"
    assert fields["title"] == "title"
    assert fields["quantity"] == "quantity"
    assert fields["list_price"] == "mrp"
    assert fields["discount_percent"] == "discountPercent"
    assert fields["quantity_available"] == "availableQuantity"
    assert fields["unit_price"] == "discountedSellingPrice"
    assert fields["weight_g"] == "weightInGms"
    assert fields["out_of_stock"] == "outOfStock"
    assert not any(issue["error_code"] == "OUT_OF_STOCK_WITH_POSITIVE_AVAILABILITY" for issue in result["issues"])
    assert result["valid_rows"] == 1


def test_zepto_price_discount_and_stock_consistency_issues_are_reported():
    result = validate_industry_csv(
        "title,mrp,discountPercent,availableQuantity,discountedSellingPrice,outOfStock\n"
        "Snack,100,120,5,110,true\n",
        profile_id="ecommerce",
    )
    codes = {issue["error_code"] for issue in result["issues"]}
    assert "DISCOUNT_PERCENT_OUT_OF_RANGE" in codes
    assert "SELLING_PRICE_ABOVE_LIST_PRICE" in codes
    assert "OUT_OF_STOCK_WITH_POSITIVE_AVAILABILITY" in codes


def test_industry_issue_metrics_count_all_findings_even_when_details_are_capped():
    rows = "".join(f"S-{index},Widget,not-a-price,USD\\n" for index in range(600))
    result = validate_industry_csv(
        "sku,title,price,currency\\n" + rows,
        profile_id="ecommerce",
    )

    assert result["metrics"]["issue_count"] == 600
    assert result["metrics"]["critical_issue_count"] == 600
    assert result["metrics"]["returned_issue_count"] == 500
    assert result["metrics"]["issues_truncated"] is True
    assert result["metrics"]["issue_counts_by_code"]["INVALID_NONNEGATIVE_NUMBER"] == 600
    assert result["metrics"]["rows_with_critical_issues"] == 600
    assert result["invalid_rows"] == 600
    assert result["valid_rows"] == 0


def test_industry_warning_only_rows_remain_valid_but_are_counted_for_review():
    result = validate_industry_csv(
        "title,mrp,discountedSellingPrice,currency\\nWidget,10,12,USD\\n",
        profile_id="ecommerce",
    )

    assert result["valid_rows"] == 1
    assert result["invalid_rows"] == 0
    assert result["metrics"]["warning_issue_count"] == 1
    assert result["metrics"]["rows_with_warning_issues"] == 1
    assert result["metrics"]["rows_with_critical_issues"] == 0


def test_duplicate_aliases_are_explicitly_reported_as_ambiguous_not_auto_mapped():
    result = validate_industry_csv(
        "sku,seller_sku,title\\nS-1,S-1,Widget\\n",
        profile_id="ecommerce",
    )

    assert "sku" not in mapped(result)
    assert "sku" in result["unmapped_headers"]
    assert "seller_sku" in result["unmapped_headers"]
    assert result["ambiguous_mappings"] == [{
        "field": "sku",
        "source_headers": ["sku", "seller_sku"],
    }]
    assert {
        item["reason"] for item in result["unmapped_header_details"]
        if item["candidate_field"] == "sku"
    } == {"ambiguous_mapping"}


def test_industry_detection_explains_weak_and_tied_evidence():
    weak = detect_industry(["id", "name"])
    assert weak["needs_confirmation"] is True
    assert weak["profile_id"] is None
    assert weak["decision_reason"] == "insufficient_industry_signals"
    assert weak["confidence_method"] == "heuristic_signal_score_not_probability"

    tied = detect_industry(["manufacturer", "mpn", "material", "diameter", "pressure_rating", "standard"])
    assert tied["needs_confirmation"] is False or tied["decision_reason"] == "ambiguous_tied_profiles"


def test_findings_include_potential_impact_without_claiming_measured_loss():
    result = validate_industry_csv(
        "sku,title,price\\nS-1,Widget,12.50\\n",
        profile_id="ecommerce",
    )
    issue = next(item for item in result["issues"] if item["error_code"] == "PRICE_CURRENCY_MISSING")
    assert "ambiguous across currencies" in issue["potential_impact"]
    assert issue["impact_basis"] == "potential_downstream_effect_not_measured"
