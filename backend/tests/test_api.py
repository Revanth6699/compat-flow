from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_import_preview_rejects_non_csv():
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("catalog.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_import_preview_valid_csv():
    payload = (
        "sku,name,manufacturer,part_number,category,compatibility\n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes,VEH-001\n"
    )
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("catalog.csv", payload.encode(), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 1
    assert data["valid_rows"] == 1
    assert data["invalid_rows"] == 0
    assert data["preview"][0]["sku"] == "SKU-1"


def test_preview_rejects_empty_file():
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


def test_preview_rejects_invalid_utf8():
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("bad.csv", b"\xff\xfe", "text/csv")},
    )
    assert response.status_code == 400


def test_preview_returns_row_errors_for_missing_required_mappings():
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={
            "file": (
                "missing-columns.csv",
                b"sku,name\nSKU-1,Brake Pad\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["invalid_rows"] == 1
    assert any("manufacturer" in issue["message"] for issue in data["row_errors"])


def test_preview_detects_duplicate_skus_within_uploaded_file():
    payload = (
        "sku,name,manufacturer,part_number,category\n"
        "SKU-1,Brake Pad,Maker A,BP-100,Brakes\n"
        "SKU-1,Brake Disc,Maker A,BD-100,Brakes\n"
    )
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("duplicates.csv", payload.encode(), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 2
    assert data["valid_rows"] == 1
    assert data["invalid_rows"] == 1
    assert data["row_errors"][0]["error_code"] == "DUPLICATE_SKU_IN_FILE"


def test_persistent_import_is_disabled_in_public_demo():
    response = client.post(
        "/api/v1/catalog/import",
        files={"file": ("catalog.csv", b"sku,name\nSKU-1,Brake Pad\n", "text/csv")},
    )
    assert response.status_code == 403
    assert "disabled in this public demo" in response.json()["detail"]


def test_import_job_status_endpoint_is_not_exposed():
    response = client.get(
        "/api/v1/catalog/import/00000000-0000-0000-0000-000000000001"
    )
    assert response.status_code == 404


def test_preview_rejects_upload_over_five_megabytes():
    oversized = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("large.csv", oversized, "text/csv")},
    )
    assert response.status_code == 413


def test_public_spreadsheet_preview_accepts_xlsx_without_authentication():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["sku", "name", "manufacturer", "part_number", "category"])
    sheet.append(["SKU-EXCEL-1", "Brake Pad", "Maker A", "BP-100", "Brakes"])
    stream = BytesIO()
    workbook.save(stream)
    response = client.post(
        "/api/v1/catalog/import/preview-records",
        files={"file": ("supplier.xlsx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "xlsx"
    assert data["record_type"] == "products"
    assert data["total_records"] == 1
    assert data["valid_records"] == 1
    assert data["persisted"] is False


def test_public_spreadsheet_preview_rejects_json():
    response = client.post(
        "/api/v1/catalog/import/preview-records",
        files={"file": ("supplier.json", b'{"items":[]}', "application/json")},
    )
    assert response.status_code == 415
