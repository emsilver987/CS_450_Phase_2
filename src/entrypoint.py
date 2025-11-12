from __future__ import annotations

import os

from fastapi import Request, Response

from src.index import app as _app
from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
from src.middleware.rate_limit import RateLimitMiddleware

# Wrap the original app without modifying existing files
app = _app

# Apply rate limiting unless explicitly disabled
disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "").lower() == "true"
rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
if not disable_rate_limit:
    app.add_middleware(
        RateLimitMiddleware,
        requests=rate_limit_requests,
        window_seconds=rate_limit_window,
    )

# Always enable JWT middleware unless explicitly disabled
disable_auth = os.getenv("DISABLE_AUTH", "").lower() == "true"
if not disable_auth:
    app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Inject baseline security headers on every response.

    - Strict-Transport-Security ensures browsers stick to HTTPS once they see it.
    - X-Content-Type-Options prevents MIME sniffing of JSON/HTML payloads.
    - Cache-Control avoids caching sensitive API responses at the edge/browser.
    """
    response: Response = await call_next(request)
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Cache-Control", "no-store")
    return response
