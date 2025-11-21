from __future__ import annotations

import os
import logging

from .index import app as _app
from .middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
from .middleware.security_headers import SecurityHeadersMiddleware
from .middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Wrap the original app without modifying existing files
app = _app

# Add security headers middleware (always enabled)
app.add_middleware(SecurityHeadersMiddleware)

# Only add JWT middleware if auth is explicitly enabled
# Auth is enabled if ENABLE_AUTH=true OR if JWT_SECRET is set
enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
jwt_secret = os.getenv("JWT_SECRET")
if enable_auth or jwt_secret:
    app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)

# Add rate limiting middleware (added last, runs first due to LIFO order)
# This prevents brute-force attacks from bypassing rate limits
disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "").lower() == "true"
if not disable_rate_limit:
    # Parse and validate rate limit configuration
    rate_limit_requests = 120  # default
    rate_limit_window = 60  # default
    
    try:
        rate_limit_requests_env = os.getenv("RATE_LIMIT_REQUESTS")
        if rate_limit_requests_env:
            rate_limit_requests = int(rate_limit_requests_env)
            if rate_limit_requests <= 0:
                logger.warning(
                    f"Invalid RATE_LIMIT_REQUESTS value: {rate_limit_requests_env}. "
                    "Must be positive. Using default: 120"
                )
                rate_limit_requests = 120
            elif rate_limit_requests > 10000:
                logger.warning(
                    f"RATE_LIMIT_REQUESTS value {rate_limit_requests} exceeds maximum (10000). "
                    "Capping to prevent memory issues. Using default: 120"
                )
                rate_limit_requests = 120
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Invalid RATE_LIMIT_REQUESTS value: {os.getenv('RATE_LIMIT_REQUESTS')}. "
            f"Error: {e}. Using default: 120"
        )
        rate_limit_requests = 120
    
    try:
        rate_limit_window_env = os.getenv("RATE_LIMIT_WINDOW_SECONDS")
        if rate_limit_window_env:
            rate_limit_window = int(rate_limit_window_env)
            if rate_limit_window <= 0:
                logger.warning(
                    f"Invalid RATE_LIMIT_WINDOW_SECONDS value: {rate_limit_window_env}. "
                    "Must be positive. Using default: 60"
                )
                rate_limit_window = 60
            elif rate_limit_window > 3600:
                logger.warning(
                    f"RATE_LIMIT_WINDOW_SECONDS value {rate_limit_window} exceeds maximum (3600). "
                    "Capping to prevent memory issues. Using default: 60"
                )
                rate_limit_window = 60
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Invalid RATE_LIMIT_WINDOW_SECONDS value: {os.getenv('RATE_LIMIT_WINDOW_SECONDS')}. "
            f"Error: {e}. Using default: 60"
        )
        rate_limit_window = 60
    
    logger.info(
        f"Rate limiting enabled: {rate_limit_requests} requests per {rate_limit_window} seconds"
    )
    app.add_middleware(
        RateLimitMiddleware,
        requests=rate_limit_requests,
        window_seconds=rate_limit_window,
    )
else:
    logger.warning("Rate limiting is DISABLED. Only use this in trusted environments.")
