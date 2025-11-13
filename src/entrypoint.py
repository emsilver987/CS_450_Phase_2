from __future__ import annotations

import os

import logging

from src.index import app as _app
from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
from src.middleware.rate_limit import RateLimitMiddleware

app = _app

logger = logging.getLogger(__name__)

# Apply rate limiting first (added last, executes first in LIFO order)
# This ensures brute-force attacks are rate-limited even if they fail auth
disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "").lower() == "true"
rate_limit_requests_default = 120
rate_limit_window_default = 60

if not disable_rate_limit:
    try:
        rate_limit_requests_env = os.getenv(
            "RATE_LIMIT_REQUESTS", str(rate_limit_requests_default)
        )
        rate_limit_requests = int(rate_limit_requests_env)
        if rate_limit_requests < 1:
            raise ValueError("RATE_LIMIT_REQUESTS must be positive")
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Invalid RATE_LIMIT_REQUESTS value; using default: %s", exc
        )
        rate_limit_requests = rate_limit_requests_default

    try:
        rate_limit_window_env = os.getenv(
            "RATE_LIMIT_WINDOW_SECONDS", str(rate_limit_window_default)
        )
        rate_limit_window = int(rate_limit_window_env)
        if rate_limit_window < 1:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be positive")
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Invalid RATE_LIMIT_WINDOW_SECONDS value; using default: %s", exc
        )
        rate_limit_window = rate_limit_window_default

    app.add_middleware(
        RateLimitMiddleware,
        requests=rate_limit_requests,
        window_seconds=rate_limit_window,
    )

# Apply JWT authentication (added second, executes after rate limiting)
enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
jwt_secret = os.getenv("JWT_SECRET")
if enable_auth or jwt_secret:
    app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)
