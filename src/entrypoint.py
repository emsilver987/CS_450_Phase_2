from __future__ import annotations

import os

import logging

from src.index import app as _app
from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.security_headers import SecurityHeadersMiddleware
from src.utils.jwt_secret import get_jwt_secret

app = _app

logger = logging.getLogger(__name__)

# Apply security headers middleware first (added first, executes last in LIFO order)
# Security headers are always enabled for all responses, including error responses
disable_security_headers = os.getenv("DISABLE_SECURITY_HEADERS", "").lower() == "true"
if not disable_security_headers:
    # Parse HSTS configuration from environment
    hsts_max_age = 31536000  # Default: 1 year
    try:
        hsts_max_age_env = os.getenv("HSTS_MAX_AGE")
        if hsts_max_age_env:
            hsts_max_age = int(hsts_max_age_env)
            if hsts_max_age < 0:
                raise ValueError("HSTS_MAX_AGE must be non-negative")
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid HSTS_MAX_AGE value; using default: %s", exc)

    hsts_include_subdomains = (
        os.getenv("HSTS_INCLUDE_SUBDOMAINS", "true").lower() == "true"
    )
    hsts_preload = os.getenv("HSTS_PRELOAD", "false").lower() == "true"

    # Parse CSP from environment (if provided)
    csp = os.getenv("CONTENT_SECURITY_POLICY")  # None if not set, uses default

    # Parse Referrer-Policy from environment
    referrer_policy = os.getenv(
        "REFERRER_POLICY", "strict-origin-when-cross-origin"
    )

    # Parse Permissions-Policy from environment (if provided)
    permissions_policy = os.getenv("PERMISSIONS_POLICY")  # None = default

    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_max_age=hsts_max_age,
        hsts_include_subdomains=hsts_include_subdomains,
        hsts_preload=hsts_preload,
        content_security_policy=csp,
        referrer_policy=referrer_policy,
        permissions_policy=permissions_policy,
    )

# Apply rate limiting (added second, executes second in LIFO order)
# This ensures brute-force attacks are rate-limited even if they fail auth
disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "").lower() == "true"
rate_limit_requests_default = 120
rate_limit_requests_max = 10000
rate_limit_window_default = 60
rate_limit_window_max = 3600

if not disable_rate_limit:
    try:
        rate_limit_requests_env = os.getenv(
            "RATE_LIMIT_REQUESTS", str(rate_limit_requests_default)
        )
        rate_limit_requests = int(rate_limit_requests_env)
        if rate_limit_requests < 1:
            raise ValueError("RATE_LIMIT_REQUESTS must be positive")
        if rate_limit_requests > rate_limit_requests_max:
            raise ValueError(
                f"RATE_LIMIT_REQUESTS exceeds maximum of {rate_limit_requests_max}"
            )
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
        if rate_limit_window > rate_limit_window_max:
            raise ValueError(
                f"RATE_LIMIT_WINDOW_SECONDS exceeds maximum of {rate_limit_window_max}"
            )
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

# Apply JWT authentication (added last, executes first in LIFO order)
# JWT secret is now retrieved from Secrets Manager (KMS-encrypted) via get_jwt_secret()
# Falls back to JWT_SECRET env var for local development
enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
jwt_secret = get_jwt_secret()  # Try Secrets Manager first, then env var
if enable_auth or jwt_secret:
    app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)
