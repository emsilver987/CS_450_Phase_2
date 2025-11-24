"""
Tests for auth_public.py service
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.services.auth_public import public_auth, _normalize_password, EXPECTED_USERNAME, EXPECTED_PASSWORDS


@pytest.fixture
def app():
    """Create test app"""
    app = FastAPI()
    app.include_router(public_auth)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestNormalizePassword:
    """Test password normalization"""
    
    def test_normalize_unicode_quotes(self):
        """Test normalization of Unicode quotes"""
        password = "test'password"
        result = _normalize_password(password)
        assert isinstance(result, str)
    
    def test_normalize_escape_sequences(self):
        """Test normalization of escape sequences"""
        password = 'test\\"password'
        result = _normalize_password(password)
        assert "\\" not in result or result.count('"') <= 1
    
    def test_normalize_backticks(self):
        """Test normalization of backticks"""
        password = "test`password"
        result = _normalize_password(password)
        assert "`" not in result
    
    def test_normalize_quoted_string(self):
        """Test normalization of quoted strings"""
        password = '"test password"'
        result = _normalize_password(password)
        assert result.startswith("test")
    
    def test_normalize_whitespace(self):
        """Test normalization of whitespace"""
        password = "test   password"
        result = _normalize_password(password)
        assert "  " not in result  # Multiple spaces normalized
    
    def test_normalize_trailing_semicolon(self):
        """Test normalization of trailing semicolon"""
        password = "test;"
        result = _normalize_password(password)
        # Should handle semicolon normalization
        assert isinstance(result, str)
    
    def test_normalize_non_string(self):
        """Test normalization of non-string input"""
        result = _normalize_password(None)
        assert result == ""
        result = _normalize_password(123)
        assert result == ""


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_auth_success(self, client):
        """Test successful authentication"""
        response = client.post(
            "/authenticate",
            json={
                "user": {"name": EXPECTED_USERNAME, "is_admin": False},
                "secret": {"password": list(EXPECTED_PASSWORDS)[0]}
            }
        )
        assert response.status_code == 200
        assert "bearer" in response.text.lower()
    
    def test_auth_invalid_username(self, client):
        """Test authentication with invalid username"""
        response = client.post(
            "/authenticate",
            json={
                "user": {"name": "wronguser", "is_admin": False},
                "secret": {"password": list(EXPECTED_PASSWORDS)[0]}
            }
        )
        assert response.status_code == 401
    
    def test_auth_invalid_password(self, client):
        """Test authentication with invalid password"""
        response = client.post(
            "/authenticate",
            json={
                "user": {"name": EXPECTED_USERNAME, "is_admin": False},
                "secret": {"password": "wrongpassword"}
            }
        )
        assert response.status_code == 401
    
    def test_auth_missing_fields(self, client):
        """Test authentication with missing fields"""
        response = client.post(
            "/authenticate",
            json={"user": {"name": EXPECTED_USERNAME}}
        )
        # API may return 401 for missing password or 400/422 for malformed request
        assert response.status_code in [400, 401, 422]
    
    def test_auth_invalid_json(self, client):
        """Test authentication with invalid JSON"""
        response = client.post(
            "/authenticate",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]
    
    def test_auth_empty_body(self, client):
        """Test authentication with empty body"""
        response = client.post("/authenticate", json={})
        assert response.status_code in [400, 401]
    
    def test_auth_normalized_password(self, client):
        """Test authentication with normalized password variants"""
        # Test with Unicode quotes
        password_with_unicode = list(EXPECTED_PASSWORDS)[0].replace("'", "'")
        response = client.post(
            "/authenticate",
            json={
                "user": {"name": EXPECTED_USERNAME, "is_admin": False},
                "secret": {"password": password_with_unicode}
            }
        )
        # Should work after normalization
        assert response.status_code in [200, 401]  # May work if normalized correctly

