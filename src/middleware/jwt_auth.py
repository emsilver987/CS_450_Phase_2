from __future__ import annotations

"""
JWT enforcement middleware for the FastAPI application.

Responsibilities:
  * Normalize incoming request paths and headers before auth checks.
  * Allow-through for the documented public endpoints (health checks, docs,
    OpenAPI schema, and authentication bootstrap).
  * Accept tokens from either the `Authorization` header (standard Bearer
    scheme) or the spec's `X-Authorization` header.
  * Delegate JWT decoding/validation to `verify_jwt_token`, attaching the claims
    to `request.state.auth` for downstream handlers.
  * Return `401 {"detail": "Unauthorized"}` for any missing, malformed, or
    expired credentials, matching the OpenAPI spec documentation.

This middleware intentionally keeps opinions minimal—revocation checks, role
enforcement, and per-route authorization occur further down the stack.
"""

import os
from typing import Iterable
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..services.auth_service import verify_jwt_token

# Public endpoints that should bypass auth
# NOTE: Keep this list aligned with the documented unauthenticated endpoints in
#       `ece461_fall_2025_openapi_spec-2.yaml`. Each entry may represent either
#       an exact path or a prefix (when ending with a slash).
DEFAULT_EXEMPT: tuple[str, ...] = (
    "/health",
    "/health/components",
    "/tracks",
    "/authenticate",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",
    "/favicon.ico",
)


def _is_exempt(path: str, exempt: Iterable[str]) -> bool:
    for p in exempt:
        if p.endswith("/") and path.startswith(p):
            return True
        if path == p:
            return True
    return False


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    JWT verifier aligned with `src/services/auth_service.py` configuration.
    """

    def __init__(self, app, exempt_paths: Iterable[str] = DEFAULT_EXEMPT) -> None:
        super().__init__(app)
        self.exempt_paths = tuple(exempt_paths)

        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.secret = os.getenv("JWT_SECRET")
        if self.algorithm != "HS256":
            raise ValueError("This middleware currently supports HS256 only.")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Prefix-safe path normalization (handles /prod/... base paths)
        raw_path = unquote(request.scope.get("path", "") or request.url.path)
        root_prefix = request.scope.get("root_path", "") or request.headers.get(
            "X-Forwarded-Prefix", ""
        )
        path = (
            raw_path[len(root_prefix) :]
            if root_prefix and raw_path.startswith(root_prefix)
            else raw_path
        )

        if _is_exempt(path, self.exempt_paths):
            return await call_next(request)

        header = request.headers.get("Authorization") or request.headers.get(
            "X-Authorization"
        )
        if not header:
            return JSONResponse(
                {"detail": "Unauthorized"},
                status_code=401,
            )

        header = header.strip()
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
        else:
            token = header

        if not token:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        payload = verify_jwt_token(token)
        if not payload:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        request.state.auth = payload
        return await call_next(request)
