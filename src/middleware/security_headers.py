from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all HTTP responses.
    
    Implements OWASP security header recommendations:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(
        self,
        app,
        *,
        hsts_max_age: int = 31536000,  # 1 year in seconds
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        content_security_policy: str | None = None,
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: str | None = None,
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.content_security_policy = content_security_policy
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Strict-Transport-Security (HSTS)
        hsts_parts = [f"max-age={self.hsts_max_age}"]
        if self.hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")
        if self.hsts_preload:
            hsts_parts.append("preload")
        response.headers["Strict-Transport-Security"] = "; ".join(hsts_parts)

        # X-Content-Type-Options: Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options: Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # X-XSS-Protection: Legacy XSS protection (for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content-Security-Policy: Control resource loading
        if self.content_security_policy:
            response.headers["Content-Security-Policy"] = self.content_security_policy
        else:
            # Default CSP: Allow same-origin, block inline scripts/styles
            # This is a permissive default - should be customized per application
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )

        # Referrer-Policy: Control referrer information
        response.headers["Referrer-Policy"] = self.referrer_policy

        # Permissions-Policy: Control browser features
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy
        else:
            # Default: Disable geolocation, microphone, camera by default
            response.headers["Permissions-Policy"] = (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=()"
            )

        return response

