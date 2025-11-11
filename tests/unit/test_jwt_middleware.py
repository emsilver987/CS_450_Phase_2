from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Type
from unittest.mock import MagicMock

import jwt
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:  # pragma: no cover
    from src.middleware.jwt_auth import JWTAuthMiddleware

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules.setdefault("boto3", MagicMock())


def _ensure_project_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _make_jwt(secret: str | None = None, **overrides) -> str:
    now = datetime.now(UTC)
    payload = {
        "user_id": "user-123",
        "username": "alice",
        "roles": ["user"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    payload.update(overrides)
    secret_key = secret or os.environ["JWT_SECRET"]
    return jwt.encode(payload, secret_key, algorithm="HS256")


def _build_scope(path: str, headers: dict[str, str] | None = None) -> dict:
    raw_headers = []
    if headers:
        raw_headers = [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in headers.items()
        ]

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "root_path": "",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }


async def _call_next(request: Request) -> Response:
    return JSONResponse({"auth": getattr(request.state, "auth", None)})


async def _receive() -> dict:
    return {"type": "http.request"}


def _dispatch(
    middleware: "JWTAuthMiddleware",
    path: str,
    headers: dict[str, str] | None = None,
) -> Response:
    async def _run() -> Response:
        scope = _build_scope(path, headers)
        request = Request(scope, _receive)
        return await middleware.dispatch(request, _call_next)

    return asyncio.run(_run())


@pytest.fixture(scope="module")
def auth_components() -> Type["JWTAuthMiddleware"]:
    _ensure_project_path()
    sys.modules.setdefault("boto3", MagicMock())
    os.environ.setdefault("JWT_SECRET", "test-secret")

    import src.services.auth_service as auth_service

    from importlib import reload

    reload(auth_service)
    auth_service.JWT_SECRET = os.environ["JWT_SECRET"]

    import src.middleware.jwt_auth as jwt_auth

    reload(jwt_auth)
    return jwt_auth.JWTAuthMiddleware


@pytest.fixture()
def middleware(auth_components: Type["JWTAuthMiddleware"]) -> "JWTAuthMiddleware":
    middleware_cls = auth_components

    async def dummy_app(scope, receive, send):
        pass

    return middleware_cls(
        dummy_app,
        exempt_paths=(
            "/health",
            "/openapi.json",
        ),
    )


def test_exempt_path_bypasses_auth(middleware: "JWTAuthMiddleware"):
    response = _dispatch(middleware, "/health")
    assert response.status_code == 200
    assert json.loads(response.body) == {"auth": None}


def test_missing_authorization_header_returns_401(middleware: "JWTAuthMiddleware"):
    response = _dispatch(middleware, "/protected")
    assert response.status_code == 401
    assert json.loads(response.body) == {"detail": "Unauthorized"}


def test_invalid_token_returns_401(middleware: "JWTAuthMiddleware"):
    response = _dispatch(
        middleware, "/protected", {"Authorization": "Bearer invalid.token"}
    )
    assert response.status_code == 401
    assert json.loads(response.body) == {"detail": "Unauthorized"}


def test_expired_token_returns_401(middleware: "JWTAuthMiddleware"):
    expired_token = _make_jwt(
        exp=int((datetime.now(UTC) - timedelta(minutes=5)).timestamp())
    )
    response = _dispatch(
        middleware,
        "/protected",
        {"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert json.loads(response.body) == {"detail": "Unauthorized"}


def test_valid_jwt_attaches_payload_to_request_state(middleware: "JWTAuthMiddleware"):
    token = _make_jwt(username="carol", roles=["admin"])
    response = _dispatch(
        middleware, "/protected", {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    auth = json.loads(response.body)["auth"]
    assert auth["username"] == "carol"
    assert auth["roles"] == ["admin"]
    assert auth["user_id"] == "user-123"


def test_valid_jwt_in_x_authorization_header(middleware: "JWTAuthMiddleware"):
    token = _make_jwt(username="dave")
    response = _dispatch(
        middleware,
        "/protected",
        {"X-Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    auth = json.loads(response.body)["auth"]
    assert auth["username"] == "dave"
