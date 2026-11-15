"""Privacy consent evidence and data-principal request intake.

This records submitted choices and requests. It does not automatically verify
identity, fulfil erasure, or decide whether a request is legally valid.
"""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import SupabaseIdentity, get_supabase_identity
from app.core.database import get_db
from app.models import DataRightsRequest, PrivacyConsentEvent

router = APIRouter(prefix="/privacy", tags=["privacy"])
NOTICE_VERSION = "2026-11-15-draft"
ALLOWED_PURPOSES = {"service_processing", "product_updates", "ai_mapping", "public_review"}


class ConsentPayload(BaseModel):
    email: EmailStr
    purposes: dict[str, bool]
    source: str = Field(default="registration", min_length=2, max_length=80)
    notice_version: str = Field(default=NOTICE_VERSION, min_length=3, max_length=40)

    @field_validator("source")
    @classmethod
    def clean_source(cls, value: str) -> str:
        return value.strip()


class WithdrawConsentPayload(BaseModel):
    purpose: str = Field(pattern="^(product_updates|ai_mapping)$")


class RightsRequestPayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    request_type: str = Field(pattern="^(access|correction|erasure|withdraw_consent|grievance)$")
    details: str = Field(min_length=10, max_length=3000)

    @field_validator("name", "details")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


@router.post("/consents", status_code=201)
def record_consent(payload: ConsentPayload, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if not payload.purposes or set(payload.purposes) - ALLOWED_PURPOSES:
        raise HTTPException(status_code=422, detail="One or more consent purposes are not supported.")
    if payload.purposes.get("service_processing") is not True:
        raise HTTPException(status_code=422, detail="Service-processing acknowledgement is required.")
    for purpose, granted in payload.purposes.items():
        db.add(PrivacyConsentEvent(
            id=uuid4(), email=email, purpose=purpose, granted=granted,
            notice_version=payload.notice_version, source=payload.source,
        ))
    db.commit()
    return {"recorded": True, "purposes": sorted(payload.purposes), "notice_version": payload.notice_version}


@router.get("/consents/mine")
def list_my_consents(identity: SupabaseIdentity = Depends(get_supabase_identity), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PrivacyConsentEvent).where(PrivacyConsentEvent.email == identity.email)
        .order_by(PrivacyConsentEvent.recorded_at.desc()).limit(200)
    ).all()
    return [{"purpose": row.purpose, "granted": row.granted, "notice_version": row.notice_version,
             "source": row.source, "recorded_at": row.recorded_at} for row in rows]


@router.post("/consents/withdraw", status_code=201)
def withdraw_consent(payload: WithdrawConsentPayload, identity: SupabaseIdentity = Depends(get_supabase_identity), db: Session = Depends(get_db)):
    db.add(PrivacyConsentEvent(
        id=uuid4(), email=identity.email, purpose=payload.purpose, granted=False,
        notice_version=NOTICE_VERSION, source="authenticated_withdrawal",
    ))
    db.commit()
    return {"withdrawn": True, "purpose": payload.purpose}


@router.post("/requests", status_code=201)
def submit_rights_request(payload: RightsRequestPayload, db: Session = Depends(get_db)):
    request = DataRightsRequest(
        id=uuid4(), name=payload.name.strip(), email=str(payload.email).strip().lower(),
        request_type=payload.request_type, details=payload.details.strip(), status="received",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return {"request_id": str(request.id), "status": request.status,
            "message": "Your request has been received. We may contact you to verify your identity before acting."}
