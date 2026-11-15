from fastapi.testclient import TestClient
import pytest

from app.core.database import get_db
from app.main import app
from app.models import DataRightsRequest, PrivacyConsentEvent


class FakePrivacyDB:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def commit(self):
        return None

    def refresh(self, item):
        return None


@pytest.fixture
def privacy_client():
    db = FakePrivacyDB()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            yield client, db
    finally:
        app.dependency_overrides.clear()


def test_records_separate_signup_consent_purposes(privacy_client):
    client, db = privacy_client
    response = client.post("/api/v1/privacy/consents", json={
        "email": "person@example.com",
        "purposes": {"service_processing": True, "product_updates": False},
        "source": "registration",
    })
    assert response.status_code == 201
    assert len(db.items) == 2
    assert all(isinstance(item, PrivacyConsentEvent) for item in db.items)
    assert {(item.purpose, item.granted) for item in db.items} == {
        ("service_processing", True), ("product_updates", False),
    }


def test_rejects_consent_without_required_service_processing(privacy_client):
    client, db = privacy_client
    response = client.post("/api/v1/privacy/consents", json={
        "email": "person@example.com",
        "purposes": {"service_processing": False, "product_updates": True},
    })
    assert response.status_code == 422
    assert db.items == []


def test_rejects_unknown_consent_purpose(privacy_client):
    client, db = privacy_client
    response = client.post("/api/v1/privacy/consents", json={
        "email": "person@example.com",
        "purposes": {"service_processing": True, "targeted_ads": True},
    })
    assert response.status_code == 422
    assert db.items == []


def test_creates_data_rights_request_intake_record(privacy_client):
    client, db = privacy_client
    response = client.post("/api/v1/privacy/requests", json={
        "name": "Test Person",
        "email": "person@example.com",
        "request_type": "access",
        "details": "Please provide a copy of my personal data.",
    })
    assert response.status_code == 201
    assert response.json()["status"] == "received"
    assert len(db.items) == 1
    assert isinstance(db.items[0], DataRightsRequest)
    assert db.items[0].email == "person@example.com"
