from datetime import datetime, timedelta, timezone\nimport json
from hashlib import sha256
import secrets
from uuid import uuid4, UUID

import httpx\nfrom fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedUser,
    SupabaseIdentity,
    get_current_user,
    get_supabase_identity,
    require_roles,
    get_active_plan,
    require_verified_supabase_email,
)
from app.core.database import get_db\nfrom app.core.config import settings\nfrom app.services.razorpay_client import razorpay_request
from app.models import Organization, Payment, PaymentWebhookEvent, Subscription, SubscriptionPlan, User, UserInvitation

router = APIRouter(prefix="/auth", tags=["authentication"])
invitation_router = APIRouter(prefix="/invitations", tags=["invitations"])


class CurrentUserResponse(BaseModel):
    id: UUID
    auth_user_id: UUID
    organization_id: UUID
    email: str
    role: str
    is_active: bool
    account_type: str = "demo"
    plan_code: str | None = None
    subscription_status: str | None = None

    model_config = ConfigDict(from_attributes=True)



class DeleteAccountRequest(BaseModel):
    confirmation: str = Field(min_length=8, max_length=32)


def _delete_supabase_user(auth_user_id: UUID) -> None:
    service_key = settings.supabase_service_role_key
    if not service_key:
        raise HTTPException(status_code=503, detail="Account deletion is not configured. The Supabase service-role key is missing.")
    try:
        response = httpx.delete(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{auth_user_id}",
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
            timeout=10.0,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Supabase could not complete account deletion. No CompatFlow database records were deleted.") from None
    if response.status_code not in {200, 204, 404}:
        raise HTTPException(status_code=502, detail="Supabase rejected account deletion. No CompatFlow database records were deleted.")


@router.delete("/account")
def delete_account(
    payload: DeleteAccountRequest,
    identity: SupabaseIdentity = Depends(get_supabase_identity),
    db: Session = Depends(get_db),
):
    """Delete the authenticated identity; owners delete their entire organization and its history."""
    profile = db.scalar(select(User).where(User.auth_user_id == identity.auth_user_id))
    if profile is None:
        if payload.confirmation != "DELETE MY ACCOUNT":
            raise HTTPException(status_code=422, detail="Type DELETE MY ACCOUNT to confirm.")
        _delete_supabase_user(identity.auth_user_id)
        return {"deleted": True, "scope": "account"}

    if profile.role == "owner":
        if payload.confirmation != "DELETE ORGANIZATION":
            raise HTTPException(status_code=422, detail="As the organization owner, type DELETE ORGANIZATION to remove the company workspace and all associated data.")
        db.scalar(select(Organization.id).where(Organization.id == profile.organization_id).with_for_update())\n        members = list(db.scalars(select(User).where(User.organization_id == profile.organization_id)).all())
        subscriptions = list(db.scalars(
            select(Subscription).where(Subscription.organization_id == profile.organization_id).with_for_update()
        ).all())
        # Stop provider-side recurring billing before deleting local subscription history.
        for subscription in subscriptions:
            if subscription.status in {"canceled", "expired", "incomplete"}:
                continue
            if subscription.provider == "razorpay" and subscription.provider_subscription_id:
                try:
                    razorpay_request(
                        "POST",
                        f"/subscriptions/{subscription.provider_subscription_id}/cancel",
                        {"cancel_at_cycle_end": False},
                    )
                except (httpx.HTTPError, ValueError, RuntimeError):
                    raise HTTPException(status_code=502, detail="The payment provider could not confirm immediate cancellation. Your organization data has not been deleted.") from None
            elif subscription.status in {"active", "trialing", "pending", "past_due"}:
                raise HTTPException(status_code=409, detail="An active external subscription cannot be safely canceled automatically. Contact support before deleting this organization.")
        # Delete every Supabase identity belonging to this organization before removing tenant data.
        for member in members:
            if member.auth_user_id:
                _delete_supabase_user(member.auth_user_id)
        db.execute(delete(Payment).where(Payment.organization_id == profile.organization_id))\n        provider_ids = [item.provider_subscription_id for item in subscriptions if item.provider_subscription_id]\n        if provider_ids:\n            for event in db.scalars(select(PaymentWebhookEvent)).all():\n                payload_text = json.dumps(event.payload, default=str)\n                if any(provider_id in payload_text for provider_id in provider_ids):\n                    db.delete(event)\n        db.execute(delete(Organization).where(Organization.id == profile.organization_id))
        db.commit()
        return {"deleted": True, "scope": "organization", "deleted_accounts": len(members)}

    if payload.confirmation != "DELETE MY ACCOUNT":
        raise HTTPException(status_code=422, detail="Type DELETE MY ACCOUNT to confirm.")
    _delete_supabase_user(identity.auth_user_id)
    db.execute(delete(User).where(User.id == profile.id, User.organization_id == profile.organization_id))
    db.commit()
    return {"deleted": True, "scope": "account"}


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Organization name must contain at least 2 non-whitespace characters.")
        return normalized


@router.post("/organization", response_model=CurrentUserResponse, status_code=201)
def create_organization_for_current_user(
    payload: OrganizationCreateRequest,
    identity: SupabaseIdentity = Depends(get_supabase_identity),
    db: Session = Depends(get_db),
):
    """Create one organization for a verified Supabase identity during self-service onboarding."""
    require_verified_supabase_email(identity)
    existing = db.scalar(select(User).where(User.auth_user_id == identity.auth_user_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This account is already linked to a CompatFlow organization.")
    organization = Organization(id=uuid4(), name=payload.name.strip())
    profile = User(
        id=uuid4(),
        organization_id=organization.id,
        auth_user_id=identity.auth_user_id,
        email=identity.email,
        role="owner",
        is_active=True,
        account_type="demo",
    )
    db.add(organization)
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Organization setup could not be completed for this account.") from None
    db.refresh(profile)
    return CurrentUserResponse(
        id=profile.id,
        auth_user_id=identity.auth_user_id,
        organization_id=profile.organization_id,
        email=profile.email,
        role=profile.role,
        is_active=profile.is_active,
        account_type=profile.account_type,
    )

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
def get_me(current: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = current.profile
    subscription, plan = get_active_plan(current, db)
    resolved_account_type = "enterprise" if plan and plan.code == "enterprise" else "subscriber" if plan else "demo"
    if profile.account_type != resolved_account_type:
        profile.account_type = resolved_account_type
        db.commit()
        db.refresh(profile)
    return CurrentUserResponse(
        id=profile.id,
        auth_user_id=current.identity.auth_user_id,
        organization_id=profile.organization_id,
        email=profile.email,
        role=profile.role,
        is_active=profile.is_active,
        account_type=resolved_account_type,
        plan_code=plan.code if plan else None,
        subscription_status=subscription.status if subscription else None,
    )



def _member_seat_limit(db: Session, organization_id: UUID) -> int | None:
    now = datetime.now(timezone.utc)
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.organization_id == organization_id,
            Subscription.status.in_(("active", "trialing")),
            (Subscription.current_period_end.is_(None)) | (Subscription.current_period_end > now),
        ).order_by(Subscription.created_at.desc())
    )
    # An unsubscribed organization gets one seat for its owner only.
    # Missing entitlement data fails closed; explicit JSON null means unlimited
    # seats (reserved for the Enterprise plan).
    if subscription is None:
        return 1
    plan = db.get(SubscriptionPlan, subscription.plan_code)
    if plan is None or not plan.is_active:
        return 1
    entitlements = plan.entitlements or {}
    if "member_seats" not in entitlements:
        return 1
    limit = entitlements["member_seats"]
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise HTTPException(status_code=503, detail="The subscription member-seat limit is misconfigured.")
    return limit


def _member_seat_usage(db: Session, organization_id: UUID) -> dict:
    limit = _member_seat_limit(db, organization_id)
    active_members = db.scalar(
        select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
    ) or 0
    now = datetime.now(timezone.utc)
    pending_invitations = db.scalar(
        select(func.count(UserInvitation.id)).where(
            UserInvitation.organization_id == organization_id,
            UserInvitation.accepted_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
    ) or 0
    occupied = active_members + pending_invitations
    return {
        "member_seat_limit": limit,
        "active_members": active_members,
        "pending_invitations": pending_invitations,
        "occupied_seats": occupied,
        "available_seats": max(0, limit - occupied) if limit is not None else None,
        "over_limit": limit is not None and occupied > limit,
        "active_members_over_limit": limit is not None and active_members > limit,
        "existing_members_retained": True,
    }


def _ensure_invitation_seat_available(
    db: Session,
    organization_id: UUID,
    *,
    include_pending_invitations: bool,
) -> None:
    limit = _member_seat_limit(db, organization_id)
    if limit is None:
        return
    active_members = db.scalar(
        select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
    ) or 0
    reserved_seats = 0
    if include_pending_invitations:
        now = datetime.now(timezone.utc)
        reserved_seats = db.scalar(
            select(func.count(UserInvitation.id)).where(
                UserInvitation.organization_id == organization_id,
                UserInvitation.accepted_at.is_(None),
                UserInvitation.revoked_at.is_(None),
                UserInvitation.expires_at > now,
            )
        ) or 0
    if active_members + reserved_seats >= limit:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "The subscription member-seat limit has been reached.",
                "member_seat_limit": limit,
                "active_members": active_members,
                "reserved_invitations": reserved_seats,
            },
        )


@invitation_router.get("/seats")
def get_member_seat_usage(
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    """Report seat usage without disabling existing members after a downgrade."""
    return _member_seat_usage(db, current.profile.organization_id)


@invitation_router.post("", response_model=InvitationCreatedResponse, status_code=201)
def create_invitation(
    payload: InvitationCreateRequest,
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    # Serialize membership reservations per organization. This closes the race
    # between simultaneous invitation requests and seat-limit checks.
    db.scalar(
        select(Organization.id)
        .where(Organization.id == current.profile.organization_id)
        .with_for_update()
    )
    _ensure_invitation_seat_available(
        db, current.profile.organization_id, include_pending_invitations=True
    )
    if current.profile.role != "owner" and payload.role == "admin":
        raise HTTPException(status_code=403, detail="Only an organization owner can invite administrators.")
    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This email is already linked to a CompatFlow organization and cannot join another organization.",
        )

    now = datetime.now(timezone.utc)
    pending = db.scalar(
        select(UserInvitation.id).where(
            UserInvitation.organization_id == current.profile.organization_id,
            func.lower(UserInvitation.email) == email,
            UserInvitation.accepted_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
    )
    if pending:
        raise HTTPException(status_code=409, detail="An active invitation already exists for this email address.")
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
    require_verified_supabase_email(identity)

    token_hash = sha256(payload.token.encode("utf-8")).hexdigest()
    invitation = db.scalar(
        select(UserInvitation)
        .where(UserInvitation.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if invitation is None or invitation.revoked_at is not None or invitation.accepted_at is not None:
        raise HTTPException(status_code=400, detail="This invitation is invalid, revoked, or already used.")
    # Serialize acceptance against other acceptances and new invitations in
    # this organization so concurrent requests cannot oversubscribe seats.
    db.scalar(
        select(Organization.id)
        .where(Organization.id == invitation.organization_id)
        .with_for_update()
    )
    if invitation.expires_at <= now:
        raise HTTPException(status_code=400, detail="This invitation has expired.")
    if invitation.email.lower() != identity.email:
        raise HTTPException(status_code=403, detail="This invitation was issued to a different email address.")

    existing = db.scalar(select(User).where(User.auth_user_id == identity.auth_user_id))
    if existing:
        raise HTTPException(status_code=409, detail="This Supabase account is already linked to a CompatFlow user.")
    _ensure_invitation_seat_available(
        db, invitation.organization_id, include_pending_invitations=False
    )

    profile = User(
        id=uuid4(),
        organization_id=invitation.organization_id,
        auth_user_id=identity.auth_user_id,
        email=identity.email,
        role=invitation.role,
        is_active=True,
        account_type="demo",
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


class MemberResponse(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|member|viewer)$")
    is_active: bool | None = None


@invitation_router.get("/members", response_model=list[MemberResponse])
def list_organization_members(
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(User)
            .where(User.organization_id == current.profile.organization_id)
            .order_by(User.created_at.asc())
        ).all()
    )


@invitation_router.patch("/members/{member_id}", response_model=MemberResponse)
def update_organization_member(
    member_id: UUID,
    payload: MemberUpdateRequest,
    current: AuthenticatedUser = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    if payload.role is None and payload.is_active is None:
        raise HTTPException(status_code=422, detail="Provide a role or active-state change.")

    member = db.scalar(
        select(User)
        .where(
            User.id == member_id,
            User.organization_id == current.profile.organization_id,
        )
        .with_for_update()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Organization member not found.")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="The organization owner cannot be modified through member management.")
    if member.id == current.profile.id:
        raise HTTPException(status_code=403, detail="You cannot change your own organization access.")
    if current.profile.role != "owner" and member.role == "admin":
        raise HTTPException(status_code=403, detail="Only the organization owner can modify an administrator.")
    if payload.role is not None:
        if payload.role == "admin" and current.profile.role != "owner":
            raise HTTPException(status_code=403, detail="Only the organization owner can assign administrator access.")
        member.role = payload.role
    if payload.is_active is not None:
        if payload.is_active and not member.is_active:
            _ensure_invitation_seat_available(
                db, current.profile.organization_id, include_pending_invitations=False
            )
        member.is_active = payload.is_active

    db.commit()
    db.refresh(member)
    return member


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
    if current.profile.role != "owner" and invitation.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Only an organization owner can revoke an administrator invitation.",
        )
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return None
