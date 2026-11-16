import base64
import hashlib
import hmac
import logging
import secrets
import time
from email.message import EmailMessage
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 - fixed Google OAuth endpoint, not a credential
TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"  # nosec B105 - fixed Google token verification endpoint, not a credential
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPE = "https://www.googleapis.com/auth/gmail.send"


class ContactNotification(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    organization: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=10, max_length=3000)
    intent: str = Field(default="general", pattern="^(general|demo)$")


def _ready():
    signing_key = settings.app_secret_key
    return all((settings.gmail_client_id, settings.gmail_client_secret,
                settings.gmail_oauth_redirect_uri, settings.gmail_sender_email)) and (
        len(signing_key) >= 32
        and signing_key not in {"local-development-only-change-me", "change-me", "secret"}
    )


def _state():
    payload = f"{int(time.time())}:{secrets.token_urlsafe(24)}"
    signature = hmac.new(settings.app_secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _valid_state(state):
    try:
        payload, signature = state.rsplit(".", 1)
        expected = hmac.new(settings.app_secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        timestamp, nonce = payload.split(":", 1)
        age = time.time() - int(timestamp)
        return hmac.compare_digest(signature, expected) and bool(nonce) and 0 <= age <= 600
    except (ValueError, TypeError):
        return False


@router.get("/gmail/oauth/start")
def gmail_oauth_start():
    if not _ready():
        raise HTTPException(503, "Gmail OAuth is not configured.")
    params = {
        "client_id": settings.gmail_client_id,
        "redirect_uri": settings.gmail_oauth_redirect_uri,
        "response_type": "code",
        "scope": f"openid email {SCOPE}",
        "access_type": "offline",
        "prompt": "consent",
        "state": _state(),
    }
    return RedirectResponse(f"{AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/gmail/oauth/callback", response_class=HTMLResponse)
async def gmail_oauth_callback(code: str | None = Query(None), state: str | None = Query(None),
                              error: str | None = Query(None)):
    headers = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"}
    if error or not code or not state or not _valid_state(state):
        raise HTTPException(400, "Google authorization was cancelled or the OAuth state is invalid.")
    if not _ready():
        raise HTTPException(503, "Gmail OAuth is not configured.")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(TOKEN_URL, data={
            "code": code, "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "redirect_uri": settings.gmail_oauth_redirect_uri,
            "grant_type": "authorization_code",
        })
        if response.status_code != 200:
            logger.warning("Google OAuth exchange failed with status %s", response.status_code)
            raise HTTPException(502, "Google authorization could not be completed.")
        tokens = response.json()
        identity_response = await client.get(TOKEN_INFO_URL, params={"id_token": tokens.get("id_token", "")})
        identity = identity_response.json() if identity_response.status_code == 200 else {}
    email = str(identity.get("email", "")).lower()
    if identity.get("email_verified") not in (True, "true") or email != settings.gmail_sender_email.lower():
        raise HTTPException(403, "Authorize using the configured CompatFlow notification Gmail account.")
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise HTTPException(409, "Google did not issue a refresh token. Revoke the existing CompatFlow grant and authorize again.")
    escaped = refresh_token.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CompatFlow Gmail authorization</title></head><body style="font-family:system-ui;max-width:760px;margin:48px auto;padding:0 20px"><h1>Gmail authorization complete</h1><p>Google authorized {email}. Copy this refresh token directly into the Render backend secret GMAIL_REFRESH_TOKEN. Do not share it or commit it.</p><textarea readonly rows="4" style="width:100%;overflow-wrap:anywhere">{escaped}</textarea><p><button onclick="navigator.clipboard.writeText(document.querySelector('textarea').value)">Copy refresh token</button></p><p>Close this page after saving the token in Render.</p></body></html>"""
    return HTMLResponse(html, headers=headers)


async def send_gmail_notification(subject: str, body: str, *, reply_to: str | None = None):
    required = (settings.gmail_client_id, settings.gmail_client_secret, settings.gmail_refresh_token,
                settings.gmail_sender_email, settings.gmail_notification_to_email)
    if not all(required):
        raise RuntimeError("Gmail notification credentials are not fully configured.")
    async with httpx.AsyncClient(timeout=15) as client:
        token = await client.post(TOKEN_URL, data={
            "client_id": settings.gmail_client_id, "client_secret": settings.gmail_client_secret,
            "refresh_token": settings.gmail_refresh_token, "grant_type": "refresh_token",
        })
        if token.status_code != 200:
            logger.error("Gmail token refresh failed with status %s", token.status_code)
            raise RuntimeError("Gmail access token could not be refreshed.")
        access_token = token.json().get("access_token")
        if not access_token:
            raise RuntimeError("Google did not return an access token.")
        message = EmailMessage()
        message["To"] = settings.gmail_notification_to_email
        message["From"] = settings.gmail_sender_email
        message["Subject"] = subject
        if reply_to:
            message["Reply-To"] = reply_to
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        sent = await client.post(SEND_URL, headers={"Authorization": f"Bearer {access_token}"}, json={"raw": raw})
        if sent.status_code not in (200, 202):
            logger.error("Gmail send failed with status %s", sent.status_code)
            raise RuntimeError("Gmail notification could not be sent.")


async def notify_demo_request(*, name: str, email: str, organization: str, role: str, message: str):
    body = f"A new CompatFlow demo access request was submitted.\n\nName: {name}\nEmail: {email}\nOrganization: {organization}\nRole: {role}\n\nMessage:\n{message}"
    await send_gmail_notification("CompatFlow — New demo access request", body, reply_to=email)


@router.post("/contact")
async def notify_contact_submission(payload: ContactNotification,
                                    x_contact_notification_secret: str | None = Header(None)):
    expected = settings.contact_notification_secret
    if not expected or not x_contact_notification_secret or not hmac.compare_digest(expected, x_contact_notification_secret):
        raise HTTPException(401, "Unauthorized.")
    subject = "CompatFlow — New demo request" if payload.intent == "demo" else "CompatFlow — New contact message"
    body = f"A new CompatFlow {payload.intent} form submission was received.\n\nName: {payload.name}\nEmail: {payload.email}\nOrganization: {payload.organization}\nRole: {payload.role}\n\nMessage:\n{payload.message}"
    try:
        await send_gmail_notification(subject, body, reply_to=str(payload.email))
    except Exception:
        logger.exception("Contact notification delivery failed.")
        return {"ok": True, "email_sent": False}
    return {"ok": True, "email_sent": True}
