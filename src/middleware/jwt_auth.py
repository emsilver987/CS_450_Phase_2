from __future__ import annotations
import os
from typing import Iterable
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..services import auth_service
from ..services.auth_service import verify_jwt_token

# Public endpoints that should bypass auth

DEFAULT_EXEMPT: tuple[str, ...] = (
    "/health",
    "/health/components",
    "/tracks",
    "/authenticate",
    "/login",
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
        self.secret = os.getenv("JWT_SECRET") or auth_service.JWT_SECRET

        if not self.secret:
            raise RuntimeError(
                "JWT_SECRET is not configured. Set the JWT_SECRET environment variable."
            )

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
