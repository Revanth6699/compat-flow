from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_current_user_requires_bearer_token():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_current_user_rejects_invalid_bearer_token():
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer definitely-not-a-valid-token"},
    )
    assert response.status_code == 401
