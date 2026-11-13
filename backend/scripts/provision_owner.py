"""Provision the first CompatFlow organization owner from a verified Supabase account.

Run from the backend directory:
    python -m scripts.provision_owner --organization-name "Your Organization"

Required environment:
    DATABASE_URL
    SUPABASE_URL
    SUPABASE_ANON_KEY
    SUPABASE_ACCESS_TOKEN

The access token is read only from the environment and is never printed.
"""
from __future__ import annotations

import argparse
import os
import sys
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Organization, User


def get_verified_supabase_identity(access_token: str) -> tuple[UUID, str]:
    """Resolve the bearer token through Supabase and require a confirmed email."""
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be configured.")

    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("Supabase could not verify the supplied access token.") from None

    user_id = payload.get("id")
    email = str(payload.get("email") or "").strip().lower()
    if not user_id or not email or not payload.get("email_confirmed_at"):
        raise RuntimeError("A valid Supabase user with a confirmed email is required.")

    try:
        return UUID(str(user_id)), email
    except ValueError:
        raise RuntimeError("Supabase returned an invalid user identifier.") from None


def provision_first_owner(
    db: Session,
    auth_user_id: UUID,
    email: str,
    organization_name: str,
) -> User:
    """Create the initial organization and owner in one database transaction."""
    normalized_email = email.strip().lower()
    normalized_name = organization_name.strip()

    if not normalized_email:
        raise ValueError("A verified email address is required.")
    if not 2 <= len(normalized_name) <= 160:
        raise ValueError("Organization name must contain between 2 and 160 characters.")

    existing_profile = db.scalar(
        select(User.id).where(User.auth_user_id == auth_user_id).limit(1)
    )
    if existing_profile is not None:
        raise RuntimeError("This Supabase account is already linked to a CompatFlow user.")

    existing_owner = db.scalar(
        select(User.id)
        .where(User.role == "owner", User.is_active.is_(True))
        .limit(1)
    )
    if existing_owner is not None:
        raise RuntimeError(
            "An active organization owner already exists. "
            "First-owner provisioning is disabled after initial setup."
        )

    organization = Organization(id=uuid4(), name=normalized_name)
    profile = User(
        id=uuid4(),
        organization_id=organization.id,
        auth_user_id=auth_user_id,
        email=normalized_email,
        role="owner",
        is_active=True,
    )
    db.add(organization)
    db.add(profile)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RuntimeError(
            "Owner provisioning conflicted with an existing database record; no changes were committed."
        ) from None

    db.refresh(profile)
    return profile


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision the first CompatFlow organization owner."
    )
    parser.add_argument(
        "--organization-name",
        required=True,
        help="Name for the initial CompatFlow organization.",
    )
    args = parser.parse_args()

    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if not access_token:
        print("SUPABASE_ACCESS_TOKEN must be set in the environment.", file=sys.stderr)
        return 2

    try:
        auth_user_id, email = get_verified_supabase_identity(access_token)
        with SessionLocal() as db:
            profile = provision_first_owner(
                db,
                auth_user_id=auth_user_id,
                email=email,
                organization_name=args.organization_name,
            )
        print(
            "Initial owner provisioned successfully. "
            f"Organization ID: {profile.organization_id}; "
            f"User profile ID: {profile.id}; Role: {profile.role}."
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"Owner provisioning failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
