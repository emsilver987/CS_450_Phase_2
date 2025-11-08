from __future__ import annotations

import os
from typing import Iterable

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.testclient import TestClient


def _is_exempt(path: str, exempt_paths: Iterable[str]) -> bool:
    # allow exact match or prefix (e.g., /health, /healthz, /health/live)
    return any(path == p or path.startswith(p.rstrip("/")) for p in exempt_paths)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, exempt_paths: Iterable[str] = ()):
        super().__init__(app)
        self.exempt_paths = tuple(exempt_paths)
        self.secret = os.getenv("JWT_SECRET", "")
        # strict by default; tests set JWT_LEEWAY_SEC=0 explicitly
        try:
            self.leeway = int(os.getenv("JWT_LEEWAY_SEC", "0"))
        except ValueError:
            self.leeway = 0

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass auth for exempt endpoints
        if _is_exempt(request.url.path, self.exempt_paths):
            return await call_next(request)

        # Expect Authorization: Bearer <token>
        auth = request.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Require HS256 + expiration claim;
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options={"require": ["exp"]},
                leeway=self.leeway,
            )
            # make user info available to routes if needed
            request.state.user = payload.get("sub")
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token expired"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            # Do not leak verification details
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


# ----------------------------- Tests ----------------------------- #

def _build_app(exempt_paths=()):
    app = FastAPI()

    @app.get("/protected")
    async def protected(request: Request):
        return {"user": getattr(request.state, "user", None)}

    @app.get("/health")
    async def health():
        return {"ok": True}

    app.add_middleware(JWTAuthMiddleware, exempt_paths=exempt_paths)
    return app


def _encode(payload, secret, *, leeway=0, expired=False):
    data = payload.copy()
    now = int(os.getenv("TEST_NOW", "0") or "0") or int(__import__("time").time())
    if expired:
        data["exp"] = now - 1
    else:
        data["exp"] = now + 60
    return jwt.encode(data, secret, algorithm="HS256")


def test_is_exempt_matches_exact_and_prefix():
    assert _is_exempt("/health", ("/health", "/metrics"))
    assert _is_exempt("/health/live", ("/health",))
    assert not _is_exempt("/api/health", ("/health",))


def test_request_without_authorization_header(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret123")
    app = _build_app()
    client = TestClient(app)

    response = client.get("/protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


def test_request_with_invalid_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret123")
    app = _build_app()
    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": "Bearer not_a_jwt"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_request_with_expired_token(monkeypatch):
    secret = "secret123"
    monkeypatch.setenv("JWT_SECRET", secret)
    token = _encode({"sub": "user1"}, secret, expired=True)
    app = _build_app()
    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_request_with_valid_token(monkeypatch):
    secret = "secret123"
    monkeypatch.setenv("JWT_SECRET", secret)
    token = _encode({"sub": "user1"}, secret)
    app = _build_app()
    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user"] == "user1"


def test_exempt_path_skips_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret123")
    app = _build_app(exempt_paths=("/health",))
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
