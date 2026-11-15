from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth


class FakeJwksClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.key)


@pytest.fixture
def signing_keys(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth.settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(auth, "_jwks_client", lambda: FakeJwksClient(private_key.public_key()))
    return private_key


def make_token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid4()),
        "email": "member@example.com",
        "aud": "authenticated",
        "iss": "https://project.supabase.co/auth/v1",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "test-key"})


def credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_supabase_token_accepts_valid_es256_signature_and_required_claims(signing_keys):
    identity = auth.get_supabase_identity(credentials(make_token(signing_keys)))
    assert identity.email == "member@example.com"
    assert identity.access_token


@pytest.mark.parametrize(
    "claim,value",
    [
        ("aud", "other"),
        ("iss", "https://attacker.example/auth/v1"),
        ("exp", int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())),
        ("sub", "not-a-uuid"),
        ("email", None),
    ],
)
def test_supabase_token_rejects_invalid_required_claims(signing_keys, claim, value):
    token = make_token(signing_keys, **{claim: value})
    with pytest.raises(HTTPException) as error:
        auth.get_supabase_identity(credentials(token))
    assert error.value.status_code == 401


def test_supabase_token_rejects_hmac_algorithm(signing_keys):
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "email": "member@example.com",
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        },
        "attacker-controlled-secret-value-with-32-plus-bytes",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        auth.get_supabase_identity(credentials(token))
    assert error.value.status_code == 401


def test_supabase_token_rejects_missing_bearer_credentials():
    with pytest.raises(HTTPException) as error:
        auth.get_supabase_identity(None)
    assert error.value.status_code == 401


def test_verified_email_check_fails_closed_when_supabase_is_unavailable(monkeypatch):
    identity = auth.SupabaseIdentity(uuid4(), "member@example.com", "token")

    def fail_request(*args, **kwargs):
        import httpx
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(auth.settings, "supabase_anon_key", "public-anon-key")
    monkeypatch.setattr(auth.httpx, "get", fail_request)

    with pytest.raises(HTTPException) as error:
        auth.require_verified_supabase_email(identity)
    assert error.value.status_code == 503
