import json

from app.services.ingestion_adapters import parse_source
from app.services.industry_catalog import validate_industry_records


def test_demo_csv_parser_accepts_more_than_ten_thousand_records():
    rows = ["product_id,product_category_name,product_weight_g"]
    rows.extend(f"p-{index},beauty,100" for index in range(10_001))
    parsed = parse_source("\n".join(rows).encode(), "products.csv", max_records=None)
    assert len(parsed.records) == 10_001


def test_demo_json_parser_accepts_more_than_ten_thousand_records():
    payload = [{"product_id": f"p-{index}"} for index in range(10_001)]
    parsed = parse_source(json.dumps(payload).encode(), "products.json", max_records=None)
    assert len(parsed.records) == 10_001


def test_demo_xml_parser_accepts_more_than_ten_thousand_records():
    records = "".join(f"<record><product_id>p-{index}</product_id></record>" for index in range(10_001))
    payload = f"<records>{records}</records>".encode()
    parsed = parse_source(payload, "products.xml", max_records=None)
    assert len(parsed.records) == 10_001


def test_demo_industry_validator_accepts_more_than_ten_thousand_records():
    headers = ["product_id", "product_category_name", "product_weight_g"]
    records = [
        {"product_id": f"p-{index}", "product_category_name": "beauty", "product_weight_g": 100}
        for index in range(10_001)
    ]
    result = validate_industry_records(headers, records, profile_id="ecommerce", max_rows=None)
    assert result["total_rows"] == 10_001
