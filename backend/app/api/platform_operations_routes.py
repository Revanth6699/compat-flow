from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.demo_routes import require_platform_admin
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.models import SupportComplaint, SubscriptionUsageEvent, Subscription

router = APIRouter(tags=["support", "platform administration"])


class ComplaintCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=5000)


class ComplaintStatusUpdate(BaseModel):
    status: str
    admin_notes: str | None = Field(default=None, max_length=5000)


@router.post("/support/complaints", status_code=201)
def submit_complaint(payload: ComplaintCreate, current: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    complaint = SupportComplaint(
        id=uuid4(),
        organization_id=current.profile.organization_id,
        user_id=current.profile.id,
        requester_name=current.profile.name or current.identity.email,
        requester_email=current.identity.email,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        status="open",
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/platform-admin/complaints")
def list_complaints(_admin: AuthenticatedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(SupportComplaint).order_by(SupportComplaint.created_at.desc()).limit(500)).all())


@router.patch("/platform-admin/complaints/{complaint_id}")
def update_complaint(complaint_id: UUID, payload: ComplaintStatusUpdate, _admin: AuthenticatedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    if payload.status not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(status_code=422, detail="Status must be open, in_progress, resolved or closed.")
    complaint = db.get(SupportComplaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    complaint.status = payload.status
    if payload.admin_notes is not None:
        complaint.admin_notes = payload.admin_notes.strip() or None
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/platform-admin/subscription-usage")
def subscription_usage(_admin: AuthenticatedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    events = list(db.execute(
        select(SubscriptionUsageEvent.event_type, func.sum(SubscriptionUsageEvent.quantity), func.count())
        .group_by(SubscriptionUsageEvent.event_type)
    ).all())
    totals = {kind: {"quantity": int(quantity or 0), "events": int(count)} for kind, quantity, count in events}
    recent = list(db.scalars(select(SubscriptionUsageEvent).order_by(SubscriptionUsageEvent.created_at.desc()).limit(200)).all())
    return {"totals": totals, "events": recent, "ledger_started_at": db.scalar(select(func.min(SubscriptionUsageEvent.created_at)))}
