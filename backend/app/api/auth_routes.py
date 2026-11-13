from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedUser,
    SupabaseIdentity,
    get_current_user,
    get_supabase_identity,
    require_roles,
)
from app.core.database import get_db
from app.models import User, UserInvitation

router = APIRouter(prefix="/auth", tags=["authentication"])
invitation_router = APIRouter(prefix="/invitations", tags=["invitations"])


class CurrentUserResponse(BaseModel):
    id: UUID
    auth_user_id: UUID
    organization_id: UUID
    email: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(admin|member|viewer)$")
    expires_in_hours: int = Field(default=72, ge=1, le=168)


class InvitationCreatedResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    invitation_token: str


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class InvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current: AuthenticatedUser = Depends(get_current_user)):
    profile = current.profile
    return CurrentUserResponse(
        id=profile.id,
        auth_user_id=current.identity.auth_user_id,
        organization_id=profile.organization_id,
        email=profile.email,
        role=profile.role,
        is_active=profile.is_active,
    )


@invitation_router.post("", response_model=InvitationCreatedResponse, status_code=201)
def create_invitation(
    payload: InvitationCreateRequest,
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    existing = db.scalar(
        select(User).where(
            User.organization_id == current.profile.organization_id,
            User.email == email,
            User.is_active.is_(True),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="This email already has access to the organization.")

    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        id=uuid4(),
        organization_id=current.profile.organization_id,
        email=email,
        role=payload.role,
        token_hash=sha256(raw_token.encode("utf-8")).hexdigest(),
        invited_by_user_id=current.profile.id,
        expires_at=now + timedelta(hours=payload.expires_in_hours),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return InvitationCreatedResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        invitation_token=raw_token,
    )


@invitation_router.post("/accept", response_model=CurrentUserResponse)
def accept_invitation(
    payload: InvitationAcceptRequest,
    identity: SupabaseIdentity = Depends(get_supabase_identity),
    db: Session = Depends(get_db),
):
    if not identity.email_verified:
        raise HTTPException(status_code=403, detail="Verify your email address with Supabase before accepting an invitation.")

    token_hash = sha256(payload.token.encode("utf-8")).hexdigest()
    invitation = db.scalar(
        select(UserInvitation)
        .where(UserInvitation.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if invitation is None or invitation.revoked_at is not None or invitation.accepted_at is not None:
        raise HTTPException(status_code=400, detail="This invitation is invalid, revoked, or already used.")
    if invitation.expires_at <= now:
        raise HTTPException(status_code=400, detail="This invitation has expired.")
    if invitation.email.lower() != identity.email:
        raise HTTPException(status_code=403, detail="This invitation was issued to a different email address.")

    existing = db.scalar(select(User).where(User.auth_user_id == identity.auth_user_id))
    if existing:
        raise HTTPException(status_code=409, detail="This Supabase account is already linked to a CompatFlow user.")

    profile = User(
        id=uuid4(),
        organization_id=invitation.organization_id,
        auth_user_id=identity.auth_user_id,
        email=identity.email,
        role=invitation.role,
        is_active=True,
    )
    invitation.accepted_at = now
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This invitation could not be accepted because the account already exists.") from None
    db.refresh(profile)
    return CurrentUserResponse(
        id=profile.id,
        auth_user_id=identity.auth_user_id,
        organization_id=profile.organization_id,
        email=profile.email,
        role=profile.role,
        is_active=profile.is_active,
    )


@invitation_router.get("", response_model=list[InvitationResponse])
def list_invitations(
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(UserInvitation)
            .where(UserInvitation.organization_id == current.profile.organization_id)
            .order_by(UserInvitation.created_at.desc())
        ).all()
    )


@invitation_router.delete("/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: UUID,
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    invitation = db.scalar(
        select(UserInvitation).where(
            UserInvitation.id == invitation_id,
            UserInvitation.organization_id == current.profile.organization_id,
        )
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="An accepted invitation cannot be revoked.")
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return None
