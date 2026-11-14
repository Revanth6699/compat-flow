from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import httpx

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import DemoAccessRequest, RolePermission, Subscription, SubscriptionPlan, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class SupabaseIdentity:
    auth_user_id: UUID
    email: str
    access_token: str


@dataclass(frozen=True)
class AuthenticatedUser:
    identity: SupabaseIdentity
    profile: User


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured.")
    return PyJWKClient(f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid Supabase access token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_supabase_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> SupabaseIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")

    try:
        token = credentials.credentials
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm not in {"ES256", "RS256"}:
            raise _unauthorized()
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud", "email"]},
        )
        email_claim = claims.get("email")
        if not isinstance(email_claim, str) or not email_claim.strip():
            raise _unauthorized()
        return SupabaseIdentity(
            auth_user_id=UUID(claims["sub"]),
            email=email_claim.strip().lower(),
            access_token=token,
        )
    except (PyJWTError, ValueError, KeyError, RuntimeError):
        raise _unauthorized() from None


def get_current_user(
    identity: SupabaseIdentity = Depends(get_supabase_identity),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    profile = db.scalar(select(User).where(User.auth_user_id == identity.auth_user_id))
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No CompatFlow organization is linked to this account yet.",
        )
    if not profile.is_active:
        raise HTTPException(status_code=403, detail="This CompatFlow account is inactive.")
    if profile.email.lower() != identity.email:
        raise HTTPException(status_code=403, detail="The authenticated email does not match the authorized account.")
    return AuthenticatedUser(identity=identity, profile=profile)


def require_roles(*roles: str):
    allowed = frozenset(roles)

    def dependency(current: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current.profile.role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
        return current

    return dependency



def require_verified_supabase_email(identity: SupabaseIdentity) -> None:
    if not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail="Email verification checks are not configured.")
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {identity.access_token}",
            },
            timeout=5.0,
        )
        response.raise_for_status()
        user_data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Could not verify the Supabase account status.") from None
    confirmed_at = user_data.get("email_confirmed_at")
    returned_email = str(user_data.get("email", "")).strip().lower()
    if not confirmed_at or returned_email != identity.email:
        raise HTTPException(status_code=403, detail="Verify your email address before continuing.")



def require_permission(permission: str):
    def dependency(
        current: AuthenticatedUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AuthenticatedUser:
        granted = db.scalar(
            select(RolePermission.id).where(
                RolePermission.role == current.profile.role,
                RolePermission.permission == permission,
            )
        )
        if granted is None:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action.",
            )
        return current

    return dependency


def get_active_plan(current: AuthenticatedUser, db: Session):
    """Resolve the active subscription for the user's organization."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.organization_id == current.profile.organization_id,
            Subscription.status.in_(("active", "trialing")),
            (Subscription.current_period_end.is_(None)) | (Subscription.current_period_end > now),
        ).order_by(Subscription.created_at.desc())
    )
    if subscription is None:
        return None, None
    plan = db.get(SubscriptionPlan, subscription.plan_code)
    if plan is None or not plan.is_active:
        return None, None
    return subscription, plan


def require_plan_feature(feature: str):
    def dependency(
        current: AuthenticatedUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AuthenticatedUser:
        subscription, plan = get_active_plan(current, db)
        if subscription is None or plan is None:
            raise HTTPException(status_code=402, detail="An active CompatFlow subscription is required to access this feature.")
        if not bool((plan.entitlements or {}).get(feature, False)):
            raise HTTPException(status_code=403, detail={
                "message": "This feature is not included in your current subscription plan.",
                "current_plan": plan.code,
                "required_feature": feature,
                "upgrade_url": "/pricing",
            })
        return current
    return dependency


def require_demo_or_paid_access():
    """Allow only a current paid CSV entitlement or an explicitly approved demo email."""
    def dependency(
        current: AuthenticatedUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AuthenticatedUser:
        subscription, plan = get_active_plan(current, db)
        if subscription is not None and plan is not None and bool((plan.entitlements or {}).get("csv_validation", False)):
            return current
        approved = db.scalar(
            select(DemoAccessRequest.id).where(
                DemoAccessRequest.email == current.identity.email,
                DemoAccessRequest.status == "approved",
            ).limit(1)
        )
        if approved is None:
            raise HTTPException(status_code=403, detail="Approved demo access or an active CSV-validation subscription is required.")
        return current
    return dependency
