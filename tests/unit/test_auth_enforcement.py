from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src import index
from src.services import auth_service


@pytest.fixture(autouse=True)
def set_jwt_secret(monkeypatch):
    monkeypatch.setattr(auth_service, "JWT_SECRET", "test-secret")
    return "test-secret"


def _make_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/artifacts",
        "headers": [],
    }
    for key, value in (headers or {}).items():
        scope["headers"].append((key.lower().encode("latin-1"), value.encode("latin-1")))

    async def receive():
        return {"type": "http.request"}

    return Request(scope, receive)


def test_verify_auth_token_missing_header():
    request = _make_request()

    with pytest.raises(HTTPException) as exc:
        index.verify_auth_token(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


def test_verify_auth_token_invalid_token():
    request = _make_request({"Authorization": "Bearer invalid.jwt.token"})

    with pytest.raises(HTTPException) as exc:
        index.verify_auth_token(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


def test_verify_auth_token_valid_token_sets_state():
    payload = {"sub": "alice"}
    token = jwt.encode(payload, auth_service.JWT_SECRET, algorithm=auth_service.JWT_ALGORITHM)
    request = _make_request({"Authorization": f"Bearer {token}"})

    assert index.verify_auth_token(request) is True
    assert request.state.auth["sub"] == "alice"

