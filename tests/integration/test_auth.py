from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import jwt
import pytest

pytest.importorskip("httpx")  # FastAPI TestClient requires httpx

from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules.setdefault("boto3", MagicMock())
sys.modules.setdefault("botocore", MagicMock())
sys.modules.setdefault("botocore.exceptions", MagicMock())
sys.modules.setdefault("requests", MagicMock())

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

mock_rating = types.ModuleType("src.services.rating")
mock_rating.run_scorer = MagicMock()
mock_rating.alias = MagicMock()
mock_rating.analyze_model_content = MagicMock()
mock_rating.router = MagicMock()
sys.modules.setdefault("src.services.rating", mock_rating)

mock_license = types.ModuleType("src.services.license_compatibility")
mock_license.extract_model_license = MagicMock(return_value=None)
mock_license.extract_github_license = MagicMock(return_value=None)
mock_license.check_license_compatibility = MagicMock(return_value=None)
sys.modules.setdefault("src.services.license_compatibility", mock_license)


@pytest.fixture()
def client_and_auth(monkeypatch):
    """Integration harness that reloads the FastAPI app with deterministic stubs."""
    monkeypatch.setenv("JWT_SECRET", "integration-secret")

    from src.services import auth_service

    importlib.reload(auth_service)
    auth_service.JWT_SECRET = "integration-secret"

    import src.index as index

    importlib.reload(index)

    monkeypatch.setattr(index, "reset_registry", MagicMock())
    monkeypatch.setattr(index, "purge_tokens", MagicMock())
    monkeypatch.setattr(index, "ensure_default_admin", MagicMock())

    return TestClient(index.app), auth_service, index


def _make_token(
    auth_service,
    *,
    roles: list[str] | None = None,
    expires_delta: timedelta = timedelta(minutes=5),
) -> str:
    """Mint a signed JWT for testing, optionally tweaking roles or expiry."""
    base_roles = roles if roles is not None else ["admin"]
    user_data = {
        "user_id": "admin-1",
        "username": "alice",
        "roles": base_roles,
        "groups": [],
    }

    if expires_delta >= timedelta(0):
        # Let the service create a standard token when it shouldn't be expired.
        token_obj = auth_service.create_jwt_token(
            user_data,
            expires_in=expires_delta,
        )
        return token_obj["token"]

    # For negative expirations, craft an already-expired token manually.
    now = datetime.now(UTC)
    payload = {
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "roles": user_data["roles"],
        "groups": user_data["groups"],
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": "expired-token",
    }
    return jwt.encode(
        payload,
        auth_service.JWT_SECRET,
        algorithm=auth_service.JWT_ALGORITHM,
    )


def test_reset_requires_admin_token(client_and_auth):
    client, auth_service, index = client_and_auth

    token = _make_token(auth_service)
    response = client.delete("/reset", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    index.reset_registry.assert_called_once()
    index.purge_tokens.assert_called_once()


def test_reset_missing_authorization_header_returns_403(client_and_auth):
    client, _auth_service, _index = client_and_auth

    response = client.delete("/reset")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication failed due to invalid or missing AuthenticationToken"
    }


def test_reset_with_expired_token_returns_403(client_and_auth):
    client, auth_service, _index = client_and_auth

    token = _make_token(auth_service, expires_delta=timedelta(minutes=-5))
    response = client.delete("/reset", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication failed due to invalid or missing AuthenticationToken"
    }


def test_reset_with_non_admin_token_returns_401(client_and_auth):
    client, auth_service, _index = client_and_auth

    token = _make_token(auth_service, roles=[])
    response = client.delete("/reset", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {
        "detail": "You do not have permission to reset the registry."
    }
