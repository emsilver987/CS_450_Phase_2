from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from unittest.mock import MagicMock
import types

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

# --- Test setup -----------------------------------------------------------------
# These tests exercise the real JWTAuthMiddleware + require_auth helper without
# hitting AWS/GitHub, so we inject lightweight stubs for the heavy dependencies
# that src.index pulls in during import.

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules.setdefault("boto3", MagicMock())
# Don't mock botocore.exceptions - we need the real ClientError for exception handling
# sys.modules.setdefault("botocore", MagicMock())
# sys.modules.setdefault("botocore.exceptions", MagicMock())
sys.modules.setdefault("requests", MagicMock())

# Stub S3 service functions used by routes so src.index imports cleanly.
mock_s3 = types.ModuleType("src.services.s3_service")
mock_s3.list_models = MagicMock(return_value={})
mock_s3.upload_model = MagicMock()
mock_s3.download_model = MagicMock()
mock_s3.reset_registry = MagicMock()
mock_s3.sync_model_lineage_to_neptune = MagicMock()
mock_s3.sync_model_lineage_from_s3 = MagicMock()
mock_s3.delete_model_from_neptune = MagicMock()
mock_s3.sync_all_models_to_neptune = MagicMock()
mock_s3.get_model_lineage_from_config = MagicMock(return_value={})
mock_s3.get_model_sizes = MagicMock(return_value={})
mock_s3.model_ingestion = MagicMock()
mock_s3.sanitize_model_id = MagicMock(side_effect=lambda value: value)
mock_s3.store_model_metadata = MagicMock()
mock_s3.get_model_metadata = MagicMock(return_value={})
mock_s3.store_generic_artifact_metadata = MagicMock()
mock_s3.get_generic_artifact_metadata = MagicMock(return_value={})
mock_s3.aws_available = MagicMock(return_value=True)
mock_s3.s3 = MagicMock()
mock_s3.ap_arn = "mock"
sys.modules.setdefault("src.services.s3_service", mock_s3)

# Stub rating service (used by /packages routes).
mock_rating = types.ModuleType("src.services.rating")
mock_rating.run_scorer = MagicMock()
mock_rating.alias = MagicMock()
mock_rating.analyze_model_content = MagicMock()
mock_rating.router = MagicMock()
sys.modules.setdefault("src.services.rating", mock_rating)

# Stub license compatibility service.
mock_license = types.ModuleType("src.services.license_compatibility")
mock_license.extract_model_license = MagicMock(return_value=None)
mock_license.extract_github_license = MagicMock(return_value=None)
mock_license.check_license_compatibility = MagicMock(return_value=None)
sys.modules.setdefault("src.services.license_compatibility", mock_license)

import src.index as index  # noqa: E402
from src.middleware.jwt_auth import JWTAuthMiddleware  # noqa: E402
from src.services import auth_service  # noqa: E402


@pytest.fixture(autouse=True)
def set_jwt_secret(monkeypatch):
    """Ensure a deterministic signing key for token generation."""
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(auth_service, "JWT_SECRET", "test-secret")
    return "test-secret"


@pytest.fixture()
def middleware() -> JWTAuthMiddleware:
    """Instantiate the middleware with a dummy ASGI app and default exemptions."""

    async def dummy_app(scope, receive, send):
        pass

    return JWTAuthMiddleware(
        dummy_app,
        exempt_paths=(
            "/health",
            "/openapi.json",
        ),
    )


# --- Helpers --------------------------------------------------------------------


def _make_request(
    path: str = "/protected", headers: dict[str, str] | None = None
) -> Request:
    """Construct a Starlette Request with the supplied headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
    }
    for key, value in (headers or {}).items():
        scope["headers"].append(
            (key.lower().encode("latin-1"), value.encode("latin-1"))
        )

    async def receive():
        return {"type": "http.request"}

    return Request(scope, receive)


def _dispatch(middleware: JWTAuthMiddleware, request: Request) -> JSONResponse:
    """Run the request through the middleware and return the downstream response."""

    async def _run() -> JSONResponse:
        async def _call_next(req: Request) -> JSONResponse:
            return JSONResponse({"ok": True})

        return await middleware.dispatch(request, _call_next)

    return asyncio.run(_run())


# --- Tests ----------------------------------------------------------------------


def test_require_auth_missing_header(middleware: JWTAuthMiddleware):
    """Requests without any auth header should be rejected with 401."""
    request = _make_request()

    response = _dispatch(middleware, request)
    assert response.status_code == 401

    with pytest.raises(HTTPException) as exc:
        index.require_auth(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


def test_require_auth_invalid_token(middleware: JWTAuthMiddleware):
    """Malformed tokens must also result in 401 responses."""
    request = _make_request(headers={"Authorization": "Bearer invalid.jwt.token"})

    response = _dispatch(middleware, request)
    assert response.status_code == 401

    with pytest.raises(HTTPException) as exc:
        index.require_auth(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


def test_require_auth_valid_token(middleware: JWTAuthMiddleware):
    """A valid JWT should populate request.state.auth for downstream handlers."""
    payload = {
        "user_id": "user-1",
        "username": "alice",
        "roles": ["admin"],
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        "jti": "token-id",
    }
    token = jwt.encode(
        payload, auth_service.JWT_SECRET, algorithm=auth_service.JWT_ALGORITHM
    )
    request = _make_request(headers={"Authorization": f"Bearer {token}"})

    response = _dispatch(middleware, request)
    assert response.status_code == 200

    auth_payload = index.require_auth(request)
    assert auth_payload["username"] == "alice"
    assert auth_payload["roles"] == ["admin"]
    assert auth_payload["jti"] == "token-id"
