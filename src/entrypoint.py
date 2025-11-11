from __future__ import annotations

import os

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
