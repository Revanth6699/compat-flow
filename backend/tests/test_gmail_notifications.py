from fastapi.testclient import TestClient

from app.api import gmail_notifications
from app.core.config import settings
from app.main import app


def test_contact_notification_requires_internal_secret(monkeypatch):
    monkeypatch.setattr(settings, "contact_notification_secret", "test-secret")
    client = TestClient(app)
    response = client.post("/api/v1/notifications/contact", json={
        "name": "Test User",
        "email": "test@example.com",
        "organization": "Example Ltd",
        "role": "Operations",
        "message": "Please contact me about CompatFlow.",
        "intent": "general",
    })
    assert response.status_code == 401


def test_contact_notification_sends_after_authorized_request(monkeypatch):
    monkeypatch.setattr(settings, "contact_notification_secret", "test-secret")
    sent = {}

    async def fake_send(subject, body, *, reply_to=None):
        sent["subject"] = subject
        sent["body"] = body
        sent["reply_to"] = reply_to

    monkeypatch.setattr(gmail_notifications, "send_gmail_notification", fake_send)
    client = TestClient(app)
    response = client.post(
        "/api/v1/notifications/contact",
        headers={"X-Contact-Notification-Secret": "test-secret"},
        json={
            "name": "Test User",
            "email": "test@example.com",
            "organization": "Example Ltd",
            "role": "Operations",
            "message": "Please contact me about CompatFlow.",
            "intent": "general",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "email_sent": True}
    assert "New contact message" in sent["subject"]
    assert "test@example.com" in sent["body"]
    assert sent["reply_to"] == "test@example.com"


def test_oauth_state_is_signed_and_time_limited(monkeypatch):
    monkeypatch.setattr(settings, "app_secret_key", "a-test-signing-key")
    state = gmail_notifications._state()
    assert gmail_notifications._valid_state(state)
    assert not gmail_notifications._valid_state(state + "tampered")


def test_demo_notification_uses_requester_as_reply_to(monkeypatch):
    import asyncio

    sent = {}

    async def fake_send(subject, body, *, reply_to=None):
        sent["subject"] = subject
        sent["body"] = body
        sent["reply_to"] = reply_to

    monkeypatch.setattr(gmail_notifications, "send_gmail_notification", fake_send)
    asyncio.run(gmail_notifications.notify_demo_request(
        name="Test User", email="client@example.com", organization="Example Ltd",
        role="Operations", message="Please arrange a product demo.",
    ))
    assert "New demo access request" in sent["subject"]
    assert sent["reply_to"] == "client@example.com"


def test_contact_notification_reports_delivery_failure(monkeypatch):
    monkeypatch.setattr(settings, "contact_notification_secret", "test-secret")

    async def fail_send(*args, **kwargs):
        raise RuntimeError("mail provider unavailable")

    monkeypatch.setattr(gmail_notifications, "send_gmail_notification", fail_send)
    client = TestClient(app)
    response = client.post(
        "/api/v1/notifications/contact",
        headers={"X-Contact-Notification-Secret": "test-secret"},
        json={
            "name": "Test User",
            "email": "test@example.com",
            "organization": "Example Ltd",
            "role": "Operations",
            "message": "Please contact me about CompatFlow.",
            "intent": "general",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "email_sent": False}
