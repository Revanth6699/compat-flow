from uuid import uuid4

import pytest

from app.models import Organization, User
from scripts.provision_owner import provision_first_owner


class FakeSession:
    def __init__(self, scalar_results):
        self.scalar_results = iter(scalar_results)
        self.added = []
        self.committed = False
        self.rolled_back = False

    def scalar(self, statement):
        return next(self.scalar_results)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, value):
        return None


def test_provision_first_owner_creates_organization_and_owner():
    auth_user_id = uuid4()
    db = FakeSession([None, None])

    profile = provision_first_owner(
        db,
        auth_user_id=auth_user_id,
        email="  OWNER@EXAMPLE.COM ",
        organization_name="  Example Organization  ",
    )

    organization = next(item for item in db.added if isinstance(item, Organization))
    assert profile.auth_user_id == auth_user_id
    assert profile.email == "owner@example.com"
    assert profile.role == "owner"
    assert profile.is_active is True
    assert profile.organization_id == organization.id
    assert organization.name == "Example Organization"
    assert db.committed is True
    assert db.rolled_back is False


def test_provision_first_owner_rejects_already_linked_account():
    db = FakeSession([uuid4()])

    with pytest.raises(RuntimeError, match="already linked"):
        provision_first_owner(
            db,
            auth_user_id=uuid4(),
            email="owner@example.com",
            organization_name="Example Organization",
        )

    assert db.added == []
    assert db.committed is False


def test_provision_first_owner_rejects_when_an_active_owner_exists():
    db = FakeSession([None, uuid4()])

    with pytest.raises(RuntimeError, match="active organization owner already exists"):
        provision_first_owner(
            db,
            auth_user_id=uuid4(),
            email="owner@example.com",
            organization_name="Example Organization",
        )

    assert db.added == []
    assert db.committed is False


@pytest.mark.parametrize("organization_name", ["", "x", "x" * 161])
def test_provision_first_owner_validates_organization_name(organization_name):
    db = FakeSession([])

    with pytest.raises(ValueError, match="Organization name"):
        provision_first_owner(
            db,
            auth_user_id=uuid4(),
            email="owner@example.com",
            organization_name=organization_name,
        )

    assert db.added == []
    assert db.committed is False
