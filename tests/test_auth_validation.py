import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request, HTTPException
from src.index import require_auth

# Mock payload
VALID_PAYLOAD = {"jti": "valid-token-id", "username": "testuser", "roles": ["user"]}

@patch("src.index.verify_jwt_token")
@patch("src.services.auth_service.consume_token_use")
def test_require_auth_valid_token(mock_consume, mock_verify):
    # Setup
    mock_verify.return_value = VALID_PAYLOAD
    mock_consume.return_value = {"token_id": "valid-token-id", "remaining_uses": 10}
    
    request = MagicMock(spec=Request)
    request.state.user = None
    request.headers = {"Authorization": "Bearer valid-token"}
    
    # Execute
    result = require_auth(request)
    
    # Verify
    assert result == VALID_PAYLOAD
    mock_consume.assert_called_with("valid-token-id")

@patch("src.index.verify_jwt_token")
@patch("src.services.auth_service.consume_token_use")
def test_require_auth_revoked_token(mock_consume, mock_verify):
    # Setup
    mock_verify.return_value = VALID_PAYLOAD
    mock_consume.return_value = None  # Simulate revoked/exhausted token
    
    request = MagicMock(spec=Request)
    request.state.user = None
    request.headers = {"Authorization": "Bearer revoked-token"}
    
    # Execute & Verify
    with pytest.raises(HTTPException) as excinfo:
        require_auth(request)
    
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Token revoked or expired"
    mock_consume.assert_called_with("valid-token-id")
