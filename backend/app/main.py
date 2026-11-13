from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from app.api.routes import router
from app.api.auth_routes import router as auth_router, invitation_router
from app.core.config import settings


class UploadBodyLimitMiddleware:
    """Cap the full multipart request body before Starlette parses the upload."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/api/v1/catalog/import/preview"
        ):
            await self.app(scope, receive, send)
            return

        content_length = dict(scope.get("headers", [])).get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    response = JSONResponse(
                        {"detail": "Request body exceeds the 5 MB upload limit."},
                        status_code=413,
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        buffered = []
        total_bytes = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total_bytes += len(message.get("body", b""))
            if total_bytes > self.max_bytes:
                response = JSONResponse(
                    {"detail": "Request body exceeds the 5 MB upload limit."},
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            buffered.append(message)
            if not message.get("more_body", False):
                break

        messages = iter(buffered)

        async def replay_receive():
            try:
                return next(messages)
            except StopIteration:
                return await receive()

        await self.app(scope, replay_receive, send)


app = FastAPI(
    title="CompatFlow API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env.lower() != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.app_env.lower() != "production" else None,
    debug=False,
)

allowed_origins = [
    origin.strip().rstrip("/")
    for origin in settings.frontend_origin.split(",")
    if origin.strip()
]

app.add_middleware(
    UploadBodyLimitMiddleware,
    max_bytes=settings.import_max_upload_bytes + 64 * 1024,
)

# Vercel preview URLs are deployment-specific. Permit only this project's
# team-owned preview hostname pattern in staging; production remains exact-origin.
staging_preview_origin_regex = (
    r"https://compat-flow-web(?:-[a-z0-9-]+)?-revanth-fbe6\.vercel\.app"
    if settings.app_env.lower() == "staging"
    else None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=staging_preview_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

allowed_hosts = [
    host.strip()
    for host in settings.allowed_hosts.split(",")
    if host.strip()
]
if allowed_hosts and "*" not in allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    if settings.app_env.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(invitation_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "CompatFlow API",
        "docs": "/docs" if settings.app_env.lower() != "production" else None,
        "mode": "public_csv_preview_only",
    }
