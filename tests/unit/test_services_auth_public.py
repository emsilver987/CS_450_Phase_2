"""
Unit tests for auth_public service
"""
import pytest
from fastapi import Request, HTTPException
from fastapi.responses import PlainTextResponse
from unittest.mock import patch, AsyncMock, MagicMock
from src.services.auth_public import (
    _authenticate,
    _normalize_password,
    authenticate,
    login_alias,
    EXPECTED_USERNAME,
    EXPECTED_PASSWORDS,
    STATIC_TOKEN
)


class TestNormalizePassword:
    """Test password normalization"""
    
    def test_normalize_password_valid(self):
        """Test normalizing a valid password"""
        password = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
        result = _normalize_password(password)
        assert result in EXPECTED_PASSWORDS
    
    def test_normalize_password_with_unicode_quotes(self):
        """Test normalizing password with unicode quotes"""
        password = "correcthorsebatterystaple123('__+@**(A;DROP TABLE packages"
        result = _normalize_password(password)
        # Should normalize unicode quotes
        assert isinstance(result, str)
    
    def test_normalize_password_with_escaped_quotes(self):
        """Test normalizing password with escaped quotes"""
        password = 'correcthorsebatterystaple123(\\"__+@**(A;DROP TABLE packages'
        result = _normalize_password(password)
        assert isinstance(result, str)
    
    def test_normalize_password_with_backticks(self):
        """Test normalizing password with backticks"""
        password = "correcthorsebatterystaple123(`__+@**(A;DROP TABLE packages"
        result = _normalize_password(password)
        # Backticks should be removed
        assert "`" not in result
    
    def test_normalize_password_with_trailing_semicolon(self):
        """Test normalizing password with trailing semicolon"""
        password = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages;"
        result = _normalize_password(password)
        # Should match password without semicolon
        assert result in EXPECTED_PASSWORDS or result + ";" in EXPECTED_PASSWORDS
    
    def test_normalize_password_non_string(self):
        """Test normalizing non-string password"""
        assert _normalize_password(None) == ""
        assert _normalize_password(123) == ""
        assert _normalize_password([]) == ""
    
    def test_normalize_password_empty(self):
        """Test normalizing empty password"""
        assert _normalize_password("") == ""
    
    def test_normalize_password_with_quotes_removed(self):
        """Test normalizing password with surrounding quotes"""
        password = '"correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"'
        result = _normalize_password(password)
        # Quotes should be removed
        assert not result.startswith('"')
        assert not result.endswith('"')


class TestAuthenticate:
    """Test _authenticate function"""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request"""
        request = MagicMock(spec=Request)
        request.json = AsyncMock()
        request.body = AsyncMock()
        return request
    
    @pytest.mark.asyncio
    async def test_authenticate_valid_credentials(self, mock_request):
        """Test authentication with valid credentials"""
        mock_request.json.return_value = {
            "user": {"name": EXPECTED_USERNAME},
            "secret": {"password": "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"}
        }
        
        response = await _authenticate(mock_request)
        
        assert isinstance(response, PlainTextResponse)
        assert "bearer " in response.body.decode()
        assert STATIC_TOKEN in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_username(self, mock_request):
        """Test authentication with invalid username"""
        mock_request.json.return_value = {
            "user": {"name": "wronguser"},
            "secret": {"password": "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"}
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(mock_request)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, mock_request):
        """Test authentication with invalid password"""
        mock_request.json.return_value = {
            "user": {"name": EXPECTED_USERNAME},
            "secret": {"password": "wrongpassword"}
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(mock_request)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_json(self, mock_request):
        """Test authentication with invalid JSON"""
        mock_request.json.side_effect = Exception("Invalid JSON")
        mock_request.body.return_value = b"invalid json"
        
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(mock_request)
        
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_authenticate_non_dict_body(self, mock_request):
        """Test authentication with non-dict body"""
        mock_request.json.return_value = "not a dict"
        
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(mock_request)
        
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_user(self, mock_request):
        """Test authentication with missing user field"""
        mock_request.json.return_value = {
            "secret": {"password": "password"}
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(mock_request)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_secret(self, mock_request):
        """Test authentication with missing secret field"""
        mock_request.json.return_value = {
            "user": {"name": EXPECTED_USERNAME}
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(mock_request)
        
        assert exc_info.value.status_code == 401


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request"""
        request = MagicMock(spec=Request)
        request.json = AsyncMock()
        request.body = AsyncMock()
        return request
    
    @pytest.mark.asyncio
    async def test_authenticate_endpoint(self, mock_request):
        """Test /authenticate endpoint"""
        mock_request.json.return_value = {
            "user": {"name": EXPECTED_USERNAME},
            "secret": {"password": "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"}
        }
        
        response = await authenticate(mock_request)
        
        assert isinstance(response, PlainTextResponse)
        assert "bearer " in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_login_alias_endpoint(self, mock_request):
        """Test /login endpoint (alias)"""
        mock_request.json.return_value = {
            "user": {"name": EXPECTED_USERNAME},
            "secret": {"password": "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"}
        }
        
        response = await login_alias(mock_request)
        
        assert isinstance(response, PlainTextResponse)
        assert "bearer " in response.body.decode()

