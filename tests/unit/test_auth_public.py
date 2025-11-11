from __future__ import annotations

import asyncio
import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any
from unittest.mock import MagicMock
import types

import pytest
from fastapi import HTTPException
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules.setdefault("boto3", MagicMock())
sys.modules.setdefault("botocore", MagicMock())
sys.modules.setdefault("botocore.exceptions", MagicMock())

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

auth_public = importlib.import_module("src.services.auth_public")
if not hasattr(auth_public, "sanitize_model_id"):
    sys.modules.setdefault("src.services.s3_service", MagicMock())


def _build_request(body: dict[str, Any]) -> Request:
    body_bytes = json.dumps(body).encode("utf-8")
    sent = {"done": False}

    async def receive() -> dict[str, Any]:
        if sent["done"]:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent["done"] = True
        return {
            "type": "http.request",
            "body": body_bytes,
            "more_body": False,
        }

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/authenticate",
        "headers": [(b"content-type", b"application/json")],
    }
    return Request(scope, receive)


def test_authenticate_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_ADMIN_SECRET_NAME", "")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    monkeypatch.setattr(auth_public, "_load_expected_passwords", lambda: {"secret"})
    monkeypatch.setattr(auth_public, "ensure_default_admin", lambda: True)
    monkeypatch.setattr(
        auth_public,
        "get_user_by_username",
        lambda username: {
            "user_id": "admin-1",
            "username": username,
            "roles": ["admin"],
            "groups": [],
        },
    )

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    monkeypatch.setattr(
        auth_public,
        "create_jwt_token",
        lambda user, expires_in=None: {
            "token": "encoded-token",
            "jti": "token-id",
            "expires_at": expires_at,
        },
    )

    recorded: list[tuple[str, str]] = []

    def fake_store(token_id: str, user: dict[str, Any], token: str, exp: datetime):
        recorded.append((token_id, token))

    monkeypatch.setattr(auth_public, "store_token", fake_store)

    request = _build_request(
        {
            "user": {"name": auth_public.EXPECTED_USERNAME, "is_admin": True},
            "secret": {"password": "secret"},
        }
    )

    response = asyncio.run(auth_public._authenticate(request))
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["token"].startswith("bearer ")
    assert payload["token_id"] == "token-id"
    assert "expires_at" in payload
    assert recorded == [("token-id", "encoded-token")]


def test_authenticate_invalid_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth_public, "_load_expected_passwords", lambda: {"secret"})

    request = _build_request(
        {
            "user": {"name": auth_public.EXPECTED_USERNAME},
            "secret": {"password": "wrong"},
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_public._authenticate(request))

    assert exc_info.value.status_code == 401
