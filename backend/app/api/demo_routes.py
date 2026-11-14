from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_active_plan, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models import DemoAccessRequest, Organization, Review, Subscription, User

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
    allowed_email = settings.platform_admin_email.strip().lower()
    if not allowed_email:
        raise HTTPException(status_code=503, detail="Platform administrator access is not configured.")
    if current.identity.email != allowed_email:
        raise HTTPException(status_code=403, detail="Platform administrator access is restricted.")
    return current


@router.post("/demo-requests", response_model=DemoRequestResponse, status_code=201)
def submit_demo_request(payload: DemoRequestPayload, db: Session = Depends(get_db)):
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
    return request




@router.get("/demo-access")
def resolve_demo_access(
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription, plan = get_active_plan(current, db)
    if subscription is not None and plan is not None and (
        bool((plan.entitlements or {}).get("csv_validation", False))
        or bool((plan.entitlements or {}).get("supplier_catalogs", False))
    ):
        return {"allowed": True, "access_type": "subscription"}
    approved = db.scalar(
        select(DemoAccessRequest.id).where(
            DemoAccessRequest.email == current.identity.email,
            DemoAccessRequest.status == "approved",
        ).limit(1)
    )
    return {"allowed": approved is not None, "access_type": "demo" if approved is not None else "none"}


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
def decide_demo_request(
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
        request.status = "approved"
    else:
        request.status = "rejected"
    if decision == "revoke":
        request.status = "revoked"
    request.reviewed_by = admin.identity.email
    request.reviewed_at = now
    db.commit()
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

