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


def test_postgres_razorpay_webhook_activates_once_and_ignores_stale_pending(monkeypatch):
    import json
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.core.database import SessionLocal, get_db
    from app.models import Organization, Payment, Subscription, SubscriptionPlan, User
    from fastapi.testclient import TestClient

    secret = "razorpay-webhook-integration-secret"
    monkeypatch.setattr(settings, "razorpay_webhook_secret", secret)
    db = SessionLocal()
    organization = Organization(name=f"Razorpay test {uuid4().hex[:8]}")
    plan = SubscriptionPlan(
        code=f"rzp-{uuid4().hex[:8]}",
        name=f"Razorpay Test Plan {uuid4().hex[:8]}",
        entitlements={"csv_validation": True},
        is_active=True,
    )
    try:
        db.add_all([organization, plan])
        db.flush()
        owner = User(
            organization_id=organization.id,
            auth_user_id=uuid4(),
            email=f"razorpay-{uuid4().hex[:8]}@example.com",
            role="owner",
            is_active=True,
            account_type="subscriber",
        )
        db.add(owner)
        db.flush()
        subscription = Subscription(
            organization_id=organization.id,
            user_id=owner.id,
            plan_code=plan.code,
            status="pending",
            provider="razorpay",
            provider_subscription_id=f"sub_{uuid4().hex}",
        )
        db.add(subscription)
        db.commit()

        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)

        payload = {
            "event": "subscription.activated",
            "payload": {
                "subscription": {"entity": {
                    "id": subscription.provider_subscription_id,
                    "current_start": int(datetime.now(timezone.utc).timestamp()),
                    "current_end": int(datetime.now(timezone.utc).timestamp()) + 2592000,
                    "cancel_at_cycle_end": False,
                }},
                "payment": {"entity": {
                    "id": f"pay_{uuid4().hex}",
                    "amount": 2700,
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                    "created_at": int(datetime.now(timezone.utc).timestamp()),
                }},
            },
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "x-razorpay-event-id": f"evt_{uuid4().hex}",
        }

        first = client.post("/api/v1/billing/webhooks/razorpay", content=raw, headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["subscription_matched"] is True
        db.refresh(subscription)
        assert subscription.status == "active"
        payment = db.query(Payment).filter(
            Payment.subscription_id == subscription.id
        ).one()
        assert payment.status == "succeeded"
        assert payment.amount_minor == 2700

        duplicate = client.post("/api/v1/billing/webhooks/razorpay", content=raw, headers=headers)
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True

        stale_payload = {
            "event": "subscription.pending",
            "payload": {"subscription": {"entity": {
                "id": subscription.provider_subscription_id,
            }}},
        }
        stale_raw = json.dumps(stale_payload, separators=(",", ":")).encode()
        stale_headers = {
            "Content-Type": "application/json",
            "X-Razorpay-Signature": hmac.new(secret.encode(), stale_raw, hashlib.sha256).hexdigest(),
            "x-razorpay-event-id": f"evt_{uuid4().hex}",
        }
        stale = client.post(
            "/api/v1/billing/webhooks/razorpay",
            content=stale_raw,
            headers=stale_headers,
        )
        assert stale.status_code == 200
        db.refresh(subscription)
        assert subscription.status == "active"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.rollback()
        db.delete(organization)
        db.delete(plan)
        db.commit()
        db.close()
