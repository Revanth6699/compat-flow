import hashlib
import hmac

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.razorpay_client import (
    verify_checkout_signature,
    verify_webhook_signature,
)


def test_razorpay_checkout_signature_uses_payment_and_subscription_ids(monkeypatch):
    secret = "test-razorpay-secret"
    monkeypatch.setattr(settings, "razorpay_key_secret", secret)
    message = b"pay_test123|sub_test123"
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    assert verify_checkout_signature("pay_test123", "sub_test123", signature)
    assert not verify_checkout_signature("pay_test123", "sub_other", signature)
    assert not verify_checkout_signature("pay_test123", "sub_test123", "0" * 64)


def test_razorpay_webhook_signature_uses_exact_raw_body(monkeypatch):
    secret = "test-webhook-secret"
    raw_body = b'{ "event" : "subscription.activated" }'
    monkeypatch.setattr(settings, "razorpay_webhook_secret", secret)
    signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(raw_body, signature)
    assert not verify_webhook_signature(raw_body.replace(b" ", b""), signature)
    assert not verify_webhook_signature(raw_body, "0" * 64)


def test_razorpay_webhook_rejects_missing_event_id(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "configured-test-secret")
    client = TestClient(app)
    response = client.post(
        "/api/v1/billing/webhooks/razorpay",
        content=b'{"event":"subscription.activated"}',
        headers={"X-Razorpay-Signature": "0" * 64},
    )
    assert response.status_code == 400
    assert "event-id" in response.json()["detail"]


def test_razorpay_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "configured-test-secret")
    client = TestClient(app)
    response = client.post(
        "/api/v1/billing/webhooks/razorpay",
        content=b'{"event":"subscription.activated"}',
        headers={
            "X-Razorpay-Signature": "0" * 64,
            "x-razorpay-event-id": "evt_test123",
        },
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


def test_billing_routes_require_authentication():
    client = TestClient(app)
    response = client.post(
        "/api/v1/billing/subscriptions",
        json={"plan_code": "starter", "billing_interval": "month", "total_count": 12},
    )
    assert response.status_code == 401
