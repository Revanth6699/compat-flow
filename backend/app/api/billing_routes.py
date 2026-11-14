from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models import Payment, PaymentWebhookEvent, Subscription, SubscriptionPlan
from app.services.razorpay_client import (
    configured_plan_id,
    razorpay_request,
    verify_checkout_signature,
    verify_webhook_signature,
)

router = APIRouter(prefix="/billing", tags=["billing"])


class CreateSubscriptionRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=32)
    billing_interval: str = Field(default="month", pattern="^(month|year)$")
    total_count: int = Field(ge=1, le=120)


class VerifyCheckoutRequest(BaseModel):
    subscription_id: UUID
    razorpay_payment_id: str = Field(min_length=5, max_length=160)
    razorpay_subscription_id: str = Field(min_length=5, max_length=160)
    razorpay_signature: str = Field(min_length=32, max_length=256)


class CancelSubscriptionRequest(BaseModel):
    cancel_at_cycle_end: bool = True


def _unix_datetime(value):
    if isinstance(value, int) and value > 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


def _subscription_status(event_type: str) -> str | None:
    return {
        "subscription.authenticated": "pending",
        "subscription.activated": "active",
        "subscription.charged": "active",
        "subscription.pending": "pending",
        "subscription.halted": "past_due",
        "subscription.paused": "past_due",
        "subscription.resumed": "active",
        "subscription.cancelled": "canceled",
        "subscription.completed": "expired",
    }.get(event_type)


@router.post("/subscriptions", status_code=201)
def create_subscription(
    payload: CreateSubscriptionRequest,
    current: AuthenticatedUser = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(status_code=503, detail="Razorpay API credentials are not configured.")
    provider_plan_id = configured_plan_id(payload.plan_code, payload.billing_interval)
    if not provider_plan_id:
        raise HTTPException(
            status_code=503,
            detail="The Razorpay plan ID for this plan and billing interval is not configured.",
        )
    plan = db.get(SubscriptionPlan, payload.plan_code)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="The requested subscription plan is unavailable.")

    existing = db.scalar(
        select(Subscription).where(
            Subscription.organization_id == current.profile.organization_id,
            Subscription.status.in_(("active", "trialing", "pending", "past_due")),
        ).order_by(Subscription.created_at.desc())
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="An existing subscription must be resolved or canceled before creating another subscription.",
        )

    local_subscription = Subscription(
        id=uuid4(),
        organization_id=current.profile.organization_id,
        user_id=current.profile.id,
        plan_code=plan.code,
        status="pending",
        billing_interval=payload.billing_interval,
        provider="razorpay",
    )
    db.add(local_subscription)
    db.commit()
    db.refresh(local_subscription)

    try:
        provider_result = razorpay_request(
            "POST",
            "/subscriptions",
            {
                "plan_id": provider_plan_id,
                "total_count": payload.total_count,
                "quantity": 1,
                "customer_notify": 1,
                "notes": {
                    "compatflow_subscription_id": str(local_subscription.id),
                    "compatflow_organization_id": str(current.profile.organization_id),
                    "compatflow_plan_code": plan.code,
                },
            },
        )
    except (httpx.HTTPError, ValueError, RuntimeError):
        local_subscription.status = "incomplete"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="Razorpay could not create the subscription. The local attempt was marked incomplete.",
        ) from None

    provider_subscription_id = provider_result.get("id")
    if not isinstance(provider_subscription_id, str) or not provider_subscription_id:
        local_subscription.status = "incomplete"
        db.commit()
        raise HTTPException(status_code=502, detail="Razorpay returned no subscription ID.")

    local_subscription.provider_subscription_id = provider_subscription_id
    local_subscription.provider_customer_id = provider_result.get("customer_id")
    db.commit()
    return {
        "local_subscription_id": str(local_subscription.id),
        "razorpay_subscription_id": provider_subscription_id,
        "razorpay_key_id": settings.razorpay_key_id,
        "plan_code": plan.code,
        "billing_interval": payload.billing_interval,
        "status": local_subscription.status,
        "short_url": provider_result.get("short_url"),
        "checkout_mode": "razorpay_subscription_checkout",
        "message": "Complete Razorpay Checkout. The plan becomes active only after verified server-side confirmation and subscription webhooks.",
    }


@router.post("/subscriptions/verify-checkout")
def verify_subscription_checkout(
    payload: VerifyCheckoutRequest,
    current: AuthenticatedUser = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.id == payload.subscription_id,
            Subscription.organization_id == current.profile.organization_id,
            Subscription.provider == "razorpay",
        )
    )
    if subscription is None or not subscription.provider_subscription_id:
        raise HTTPException(status_code=404, detail="Pending Razorpay subscription not found.")
    if subscription.provider_subscription_id != payload.razorpay_subscription_id:
        raise HTTPException(status_code=400, detail="The Razorpay subscription does not match this checkout attempt.")
    if not verify_checkout_signature(
        payload.razorpay_payment_id,
        subscription.provider_subscription_id,
        payload.razorpay_signature,
    ):
        raise HTTPException(status_code=400, detail="Razorpay checkout signature verification failed.")

    # Checkout verification alone does not grant access; wait for subscription.activated.
    return {
        "verified": True,
        "subscription_id": str(subscription.id),
        "status": subscription.status,
        "activation_source": "razorpay_webhook",
        "message": "Checkout signature verified. Final activation is controlled by Razorpay subscription webhooks.",
    }


@router.post("/subscriptions/{subscription_id}/cancel")
def cancel_subscription(
    subscription_id: UUID,
    payload: CancelSubscriptionRequest,
    current: AuthenticatedUser = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.organization_id == current.profile.organization_id,
            Subscription.provider == "razorpay",
        )
    )
    if subscription is None or not subscription.provider_subscription_id:
        raise HTTPException(status_code=404, detail="Razorpay subscription not found.")
    if subscription.status in {"canceled", "expired", "incomplete"}:
        return {"subscription_id": str(subscription.id), "status": subscription.status}

    try:
        razorpay_request(
            "POST",
            f"/subscriptions/{subscription.provider_subscription_id}/cancel",
            {"cancel_at_cycle_end": payload.cancel_at_cycle_end},
        )
    except (httpx.HTTPError, ValueError, RuntimeError):
        raise HTTPException(status_code=502, detail="Razorpay could not process the cancellation request.") from None

    subscription.cancel_at_period_end = payload.cancel_at_cycle_end
    # Keep the current entitlement state until Razorpay confirms cancellation.
    db.commit()
    return {
        "subscription_id": str(subscription.id),
        "cancel_at_cycle_end": subscription.cancel_at_period_end,
        "status": subscription.status,
        "message": "Cancellation request accepted by Razorpay; final state will be synchronized by webhook.",
    }


@router.get("/subscription")
def get_current_subscription(
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.organization_id == current.profile.organization_id,
            Subscription.status.in_(("pending", "trialing", "active", "past_due", "canceled", "expired", "incomplete")),
        ).order_by(Subscription.created_at.desc())
    )
    if subscription is None:
        return {"subscription": None}
    return {
        "subscription": {
            "id": str(subscription.id),
            "plan_code": subscription.plan_code,
            "provider": subscription.provider,
            "status": subscription.status,
            "billing_interval": subscription.billing_interval,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
        }
    }


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str | None = Header(default=None, alias="x-razorpay-event-id"),
    db: Session = Depends(get_db),
):
    if not settings.razorpay_webhook_secret:
        raise HTTPException(status_code=503, detail="Razorpay webhook secret is not configured.")
    if not x_razorpay_event_id or len(x_razorpay_event_id) > 180:
        raise HTTPException(status_code=400, detail="A valid x-razorpay-event-id header is required.")

    raw_chunks = bytearray()
    async for chunk in request.stream():
        raw_chunks.extend(chunk)
        if len(raw_chunks) > 1024 * 1024:
            raise HTTPException(status_code=413, detail="Razorpay webhook payload exceeds 1 MB.")
    raw_body = bytes(raw_chunks)
    if not verify_webhook_signature(raw_body, x_razorpay_signature or ""):
        raise HTTPException(status_code=400, detail="Razorpay webhook signature verification failed.")

    try:
        import json
        event_payload = json.loads(raw_body)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Razorpay webhook payload is not valid JSON.") from None
    if not isinstance(event_payload, dict) or not isinstance(event_payload.get("event"), str):
        raise HTTPException(status_code=400, detail="Razorpay webhook event payload is invalid.")

    existing_event = db.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == "razorpay",
            PaymentWebhookEvent.provider_event_id == x_razorpay_event_id,
        )
    )
    if existing_event is not None:
        return {"received": True, "duplicate": True}

    event_type = event_payload["event"]
    webhook_event = PaymentWebhookEvent(
        id=uuid4(),
        provider="razorpay",
        provider_event_id=x_razorpay_event_id,
        event_type=event_type,
        processing_status="processing",
        payload={"event": event_type},
    )
    db.add(webhook_event)

    payload = event_payload.get("payload") or {}
    subscription_entity = ((payload.get("subscription") or {}).get("entity") or {})
    provider_subscription_id = subscription_entity.get("id")
    subscription = None
    if isinstance(provider_subscription_id, str):
        subscription = db.scalar(
            select(Subscription).where(
                Subscription.provider == "razorpay",
                Subscription.provider_subscription_id == provider_subscription_id,
            ).with_for_update()
        )

    new_status = _subscription_status(event_type)
    if subscription is not None and new_status is not None:
        terminal_status = subscription.status in {"canceled", "expired"}
        stale_pending_event = new_status == "pending" and subscription.status in {"active", "past_due"}
        if not terminal_status and not stale_pending_event:
            subscription.status = new_status
            subscription.current_period_start = _unix_datetime(subscription_entity.get("current_start"))
            subscription.current_period_end = _unix_datetime(subscription_entity.get("current_end"))
            subscription.cancel_at_period_end = bool(
                subscription_entity.get("cancel_at_cycle_end", subscription.cancel_at_period_end)
            )
            if new_status == "canceled":
                subscription.canceled_at = datetime.now(timezone.utc)

    payment_entity = ((payload.get("payment") or {}).get("entity") or {})
    provider_payment_id = payment_entity.get("id")
    if subscription is not None and isinstance(provider_payment_id, str):
        payment = db.scalar(
            select(Payment).where(
                Payment.provider == "razorpay",
                Payment.provider_payment_id == provider_payment_id,
            )
        )
        payment_status = {
            "captured": "succeeded",
            "authorized": "pending",
            "failed": "failed",
            "refunded": "refunded",
        }.get(payment_entity.get("status"), "pending")
        if payment is None:
            payment = Payment(
                id=uuid4(),
                organization_id=subscription.organization_id,
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                provider="razorpay",
                provider_payment_id=provider_payment_id,
                amount_minor=int(payment_entity.get("amount") or 0),
                currency=str(payment_entity.get("currency") or "INR").upper(),
                status=payment_status,
                payment_method_type=payment_entity.get("method"),
                failure_code=payment_entity.get("error_code"),
                failure_message=payment_entity.get("error_description"),
                paid_at=_unix_datetime(payment_entity.get("created_at")) if payment_status == "succeeded" else None,
            )
            db.add(payment)
        else:
            payment.status = payment_status
            if payment_status == "succeeded":
                payment.paid_at = _unix_datetime(payment_entity.get("created_at"))

    webhook_event.processing_status = "processed"
    webhook_event.processed_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.scalar(
            select(PaymentWebhookEvent.id).where(
                PaymentWebhookEvent.provider == "razorpay",
                PaymentWebhookEvent.provider_event_id == x_razorpay_event_id,
            )
        )
        if duplicate is not None:
            return {"received": True, "duplicate": True}
        raise HTTPException(status_code=409, detail="Razorpay webhook could not be persisted safely.") from None

    return {
        "received": True,
        "duplicate": False,
        "event": event_type,
        "subscription_matched": subscription is not None,
    }
