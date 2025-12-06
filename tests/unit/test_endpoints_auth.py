"""
Tests for Auth endpoints/features
"""
import pytest
from unittest.mock import patch, MagicMock
from tests.unit.test_index_shared import (
    client, mock_auth, mock_s3_service, mock_artifact_storage,
    reset_rating_state, TEST_MODEL_ID, TEST_MODEL_NAME,
    TEST_DATASET_ID, TEST_DATASET_NAME, TEST_CODE_ID, TEST_CODE_NAME,
    RATING_STATUS_PENDING, RATING_STATUS_COMPLETED, RATING_STATUS_FAILED,
    RATING_STATUS_DISQUALIFIED
)
from unittest.mock import patch, MagicMock


class TestVerifyAuthToken:
    """Additional tests for verify_auth_token"""

    def test_verify_auth_token_bearer_prefix(self):
        """Test verify_auth_token with Bearer prefix"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        # Headers are case-insensitive, so check both x-authorization and authorization
        # Use valid JWT format (3 parts separated by dots)
        valid_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.test"

        def header_get(key, default=None):
            key_lower = key.lower()
            if key_lower == "x-authorization":
                return f"Bearer {valid_jwt}"
            elif key_lower == "authorization":
                return f"Bearer {valid_jwt}"
            return default

        request.headers.get = header_get

        with patch("src.index.verify_jwt_token", return_value={"user_id": "test"}):
            result = verify_auth_token(request)
            assert result is True

    def test_verify_auth_token_raw_jwt(self):
        """Test verify_auth_token with raw JWT (no Bearer prefix)"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        # Use valid JWT format (3 parts separated by dots)
        valid_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.test"
        request.headers.get.return_value = valid_jwt

        with patch("src.index.verify_jwt_token", return_value={"user_id": "test"}):
            result = verify_auth_token(request)
            assert result is True

    def test_verify_auth_token_invalid_format(self):
        """Test verify_auth_token with invalid JWT format"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        request.headers.get.return_value = "invalid.token"  # Only 2 parts

        result = verify_auth_token(request)
        assert result is False



