import hashlib
import hmac
from typing import Any

import httpx

from app.core.config import settings


RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


def verify_checkout_signature(payment_id: str, subscription_id: str, signature: str) -> bool:
    if not settings.razorpay_key_secret or not payment_id or not subscription_id:
        return False
    message = f"{payment_id}|{subscription_id}".encode("utf-8")
    expected = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    if not settings.razorpay_webhook_secret or not signature:
        return False
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def configured_plan_id(plan_code: str, billing_interval: str) -> str | None:
    import json

    try:
        configured = json.loads(settings.razorpay_plan_ids_json or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(configured, dict):
        return None
    value = configured.get(f"{plan_code}:{billing_interval}")
    return value.strip() if isinstance(value, str) and value.strip() else None


def razorpay_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise RuntimeError("Razorpay API credentials are not configured.")
    response = httpx.request(
        method,
        f"{RAZORPAY_API_BASE}{path}",
        json=payload,
        auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Razorpay returned an invalid response.")
    return data
