from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class SupabaseIdentity:
    auth_user_id: UUID
    email: str
    email_verified: bool


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
        return SupabaseIdentity(
            auth_user_id=UUID(claims["sub"]),
            email=str(claims["email"]).strip().lower(),
            email_verified=claims.get("email_verified") is True,
        )
    except (PyJWTError, ValueError, KeyError, RuntimeError):
        raise _unauthorized() from None


def get_current_user(
    identity: SupabaseIdentity = Depends(get_supabase_identity),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    profile = db.scalar(select(User).where(User.auth_user_id == identity.auth_user_id))
    if profile is None or not profile.is_active:
        raise HTTPException(status_code=403, detail="This account has no active CompatFlow access.")
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
