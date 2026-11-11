from fastapi.testclient import TestClient
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
        "SKU-1,Brake Pad,Maker A, BP-100,Brakes,VEH-001\n"
    )
    response = client.post(
        "/api/v1/catalog/import/preview",
        files={"file": ("catalog.csv", payload.encode(), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 1
    assert data["valid_rows"] == 1
