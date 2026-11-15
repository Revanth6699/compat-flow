from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app


class FakeDb:
    def __init__(self, approved=False, subscribed=False):
        self.approved = approved
        self.subscribed = subscribed

    def scalar(self, statement):
        sql = str(statement).lower()
        if "subscriptions" in sql:
            return SimpleNamespace(plan_code="starter") if self.subscribed else None
        if "demo_access_requests" in sql:
            return uuid4() if self.approved else None
        return None

    def get(self, model, key):
        if self.subscribed:
            return SimpleNamespace(is_active=True, entitlements={"csv_validation": True})
        return None


@pytest.fixture
def client_factory():
    def make_client(db):
        current = SimpleNamespace(
            identity=SimpleNamespace(email="approved@example.com"),
            profile=SimpleNamespace(organization_id=uuid4(), id=uuid4()),
        )
        app.dependency_overrides[get_current_user] = lambda: current
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)

    yield make_client
    app.dependency_overrides.clear()


def csv_file():
    return {"file": ("catalog.csv", b"sku,name,manufacturer,part_number,category\nS1,Brake Pad,Maker,BP-1,Brakes\n", "text/csv")}


def test_approved_demo_user_can_use_stateless_preview(client_factory):
    with client_factory(FakeDb(approved=True)) as client:
        response = client.post("/api/v1/catalog/import/preview", files=csv_file())
    assert response.status_code == 200
    assert response.json()["total_rows"] == 1


def test_unapproved_user_cannot_use_stateless_preview(client_factory):
    with client_factory(FakeDb(approved=False)) as client:
        response = client.post("/api/v1/catalog/import/preview", files=csv_file())
    assert response.status_code == 403
    assert "Approved demo access" in response.json()["detail"]


def test_subscribed_user_uses_subscription_validation_route(client_factory):
    with client_factory(FakeDb(subscribed=True)) as client:
        response = client.post("/api/v1/catalog/import/validate", files=csv_file())
    assert response.status_code == 200
    assert response.json()["total_rows"] == 1


def test_revoked_demo_user_is_denied_after_access_status_changes(client_factory):
    with client_factory(FakeDb(approved=False)) as client:
        response = client.post("/api/v1/catalog/import/profile", files=csv_file())
    assert response.status_code == 403
