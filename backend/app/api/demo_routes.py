from datetime import datetime, timezone
import logging
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_active_plan, get_current_user, is_platform_admin, resolve_import_limits, require_verified_supabase_email
from app.core.config import settings
from app.core.database import get_db
from app.models import DemoAccessRequest, Organization, Review, Subscription, User
from app.api.gmail_notifications import notify_demo_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo access", "platform administration"])


class DemoRequestPayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    organization: str = Field(min_length=2, max_length=160)
    role: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=10, max_length=3000)

    @field_validator("name", "organization", "role", "message")
    @classmethod
    def trim_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class DemoRequestResponse(BaseModel):
    id: UUID
    name: str
    email: str
    organization: str
    role: str
    message: str
    status: str
    created_at: datetime


def require_platform_admin(current: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not settings.platform_admin_email.strip():
        raise HTTPException(status_code=503, detail="Platform administrator access is not configured.")
    if not is_platform_admin(current):
        raise HTTPException(status_code=403, detail="Platform administrator access is restricted.")
    require_verified_supabase_email(current.identity)
    return current


async def sync_demo_request_to_supabase(
    request: DemoAccessRequest,
    decision: str,
    reviewed_at: datetime,
) -> None:
    """Idempotently mirror a demo request and its access decision into Supabase."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=503, detail="Supabase demo-request synchronization is not configured.")
    base_url = settings.supabase_url.rstrip("/") + "/rest/v1"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    contact_status = {
        "approve": "approved",
        "revoke": "declined",
        "reject": "declined",
    }[decision]
    contact_record = {
        "id": str(request.id),
        "name": request.name,
        "email": request.email,
        "organization": request.organization,
        "role": request.role,
        "message": request.message,
        "intent": "demo",
        "status": contact_status,
        "created_at": request.created_at.isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            contact_response = await client.post(
                f"{base_url}/contact_requests",
                params={"on_conflict": "id"},
                headers=headers,
                json=contact_record,
            )
            if contact_response.status_code not in (200, 201, 204):
                logger.error(
                    "Supabase demo-request mirror failed with status %s: %s",
                    contact_response.status_code,
                    contact_response.text[:500],
                )
                raise HTTPException(status_code=503, detail="Demo request history could not be synchronized to Supabase. Please retry.")
            if decision in {"approve", "revoke"}:
                access_record: dict[str, str | None] = {
                    "email": request.email,
                    "status": "approved" if decision == "approve" else "revoked",
                }
                if decision == "approve":
                    access_record["invited_at"] = reviewed_at.isoformat()
                    access_record["expires_at"] = None
                access_response = await client.post(
                    f"{base_url}/demo_access",
                    params={"on_conflict": "email"},
                    headers=headers,
                    json=access_record,
                )
                if access_response.status_code not in (200, 201, 204):
                    logger.error(
                        "Supabase demo-access mirror failed with status %s: %s",
                        access_response.status_code,
                        access_response.text[:500],
                    )
                    raise HTTPException(status_code=503, detail="Demo access could not be synchronized to Supabase. Please retry.")
    except httpx.HTTPError:
        logger.exception("Supabase demo workflow synchronization request failed.")
        raise HTTPException(status_code=503, detail="Supabase synchronization is temporarily unavailable. Please retry.")


@router.post("/demo-requests", response_model=DemoRequestResponse, status_code=201)
async def submit_demo_request(payload: DemoRequestPayload, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    pending = db.scalar(select(DemoAccessRequest).where(
        DemoAccessRequest.email == email,
        DemoAccessRequest.status == "pending",
    ))
    if pending:
        return pending
    request = DemoAccessRequest(
        id=uuid4(), name=payload.name, email=email,
        organization=payload.organization, role=payload.role,
        message=payload.message, status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    try:
        await notify_demo_request(
            name=request.name, email=request.email, organization=request.organization,
            role=request.role, message=request.message,
        )
    except Exception:
        logger.exception("Demo request was saved, but its email notification failed.")
    return request


@router.get("/demo-access")
def resolve_demo_access(
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        limits = resolve_import_limits(current, db)
    except HTTPException as exc:
        if exc.status_code == 403:
            return {"allowed": False, "access_type": "none"}
        raise
    return {"allowed": True, **limits}


@router.get("/demo-requests/mine")
def my_demo_request(current: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    request = db.scalar(
        select(DemoAccessRequest)
        .where(DemoAccessRequest.email == current.identity.email)
        .order_by(DemoAccessRequest.created_at.desc())
        .limit(1)
    )
    if request is None:
        return {"status": "not_requested", "approved": False}
    return {"status": request.status, "approved": request.status == "approved", "created_at": request.created_at}


@router.get("/platform-admin/demo-requests", response_model=list[DemoRequestResponse])
def list_demo_requests(
    _admin: AuthenticatedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(DemoAccessRequest).order_by(DemoAccessRequest.created_at.desc()).limit(500)).all())


@router.patch("/platform-admin/demo-requests/{request_id}/{decision}", response_model=DemoRequestResponse)
async def decide_demo_request(
    request_id: UUID,
    decision: str,
    admin: AuthenticatedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    if decision not in {"approve", "revoke", "reject"}:
        raise HTTPException(status_code=422, detail="Decision must be approve, revoke or reject.")
    request = db.get(DemoAccessRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Demo request not found.")
    now = datetime.now(timezone.utc)
    requests_to_sync: list[tuple[DemoAccessRequest, str]] = []
    if decision == "revoke":
        active_approvals = db.scalars(
            select(DemoAccessRequest).where(
                DemoAccessRequest.email == request.email,
                DemoAccessRequest.status == "approved",
            )
        ).all()
        for approval in active_approvals:
            approval.status = "revoked"
            approval.reviewed_by = admin.identity.email
            approval.reviewed_at = now
            requests_to_sync.append((approval, "revoke"))
        if request not in active_approvals:
            request.status = "revoked"
            request.reviewed_by = admin.identity.email
            request.reviewed_at = now
            requests_to_sync.append((request, "revoke"))
    elif decision == "approve":
        previous_approvals = db.scalars(
            select(DemoAccessRequest).where(
                DemoAccessRequest.email == request.email,
                DemoAccessRequest.status == "approved",
                DemoAccessRequest.id != request.id,
            )
        ).all()
        for approval in previous_approvals:
            approval.status = "revoked"
            approval.reviewed_by = admin.identity.email
            approval.reviewed_at = now
            requests_to_sync.append((approval, "revoke"))
        request.status = "approved"
        requests_to_sync.append((request, "approve"))
    else:
        request.status = "rejected"
        requests_to_sync.append((request, "reject"))
    request.reviewed_by = admin.identity.email
    request.reviewed_at = now
    try:
        db.flush()
        for item, item_decision in requests_to_sync:
            await sync_demo_request_to_supabase(item, item_decision, now)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(request)
    return request


@router.get("/platform-admin/overview")
def platform_admin_overview(
    _admin: AuthenticatedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    def count(model):
        return int(db.scalar(select(func.count()).select_from(model)) or 0)
    return {
        "users": count(User),
        "active_users": int(db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0),
        "organizations": count(Organization),
        "subscriptions": count(Subscription),
        "active_subscriptions": int(db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status.in_(("active", "trialing")))) or 0),
        "reviews": count(Review),
        "demo_requests": count(DemoAccessRequest),
        "pending_demo_requests": int(db.scalar(select(func.count()).select_from(DemoAccessRequest).where(DemoAccessRequest.status == "pending")) or 0),
        "approved_demo_requests": int(db.scalar(select(func.count()).select_from(DemoAccessRequest).where(DemoAccessRequest.status == "approved")) or 0),
        "complaints": None,
        "complaints_note": "Complaint tracking is not implemented yet.",
        "subscription_usage": None,
        "subscription_usage_note": "Monthly validation/storage usage is not yet persisted as a usage ledger, so usage totals are unavailable.",
    }
