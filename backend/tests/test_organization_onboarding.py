from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import auth_routes
from app.core.auth import SupabaseIdentity


class OnboardingDB:
    def __init__(self, existing=None, fail_commit=False):
        self.existing = existing
        self.fail_commit = fail_commit
        self.added = []
        self.committed = False
        self.rolled_back = False

    def scalar(self, statement):
        return self.existing

    def add(self, value):
        self.added.append(value)

    def commit(self):
        if self.fail_commit:
            from sqlalchemy.exc import IntegrityError
            raise IntegrityError("insert", {}, Exception("duplicate"))
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, value):
        return None


def make_identity():
    return SupabaseIdentity(
        auth_user_id=uuid4(),
        email="owner@example.com",
        access_token="verified-access-token",
    )


def test_verified_first_user_creates_owner_and_organization(monkeypatch):
    identity = make_identity()
    db = OnboardingDB()
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)

    response = auth_routes.create_organization_for_current_user(
        auth_routes.OrganizationCreateRequest(name="  Example Org  "),
        identity,
        db,
    )

    organization = next(item for item in db.added if isinstance(item, auth_routes.Organization))
    profile = next(item for item in db.added if isinstance(item, auth_routes.User))
    assert organization.name == "Example Org"
    assert profile.organization_id == organization.id
    assert profile.auth_user_id == identity.auth_user_id
    assert profile.email == identity.email
    assert profile.role == "owner"
    assert profile.is_active is True
    assert response.organization_id == organization.id
    assert db.committed is True


def test_existing_identity_cannot_create_second_organization(monkeypatch):
    identity = make_identity()
    db = OnboardingDB(existing=SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)

    with pytest.raises(HTTPException) as error:
        auth_routes.create_organization_for_current_user(
            auth_routes.OrganizationCreateRequest(name="Second Org"),
            identity,
            db,
        )

    assert error.value.status_code == 409
    assert db.added == []
    assert db.committed is False


def test_database_uniqueness_race_rolls_back_on_duplicate_identity(monkeypatch):
    identity = make_identity()
    db = OnboardingDB(fail_commit=True)
    monkeypatch.setattr(auth_routes, "require_verified_supabase_email", lambda _: None)

    with pytest.raises(HTTPException) as error:
        auth_routes.create_organization_for_current_user(
            auth_routes.OrganizationCreateRequest(name="Example Org"),
            identity,
            db,
        )

    assert error.value.status_code == 409
    assert db.rolled_back is True
    assert db.committed is False


@pytest.mark.parametrize("name", ["", " ", "  x  "])
def test_organization_name_rejects_blank_or_too_short_values(name):
    with pytest.raises(ValueError):
        auth_routes.OrganizationCreateRequest(name=name)
