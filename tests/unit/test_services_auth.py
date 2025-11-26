"""
Unit tests for auth_service
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import jwt


class TestAuthService:
    """Test authentication service"""
    
    def test_hash_password(self):
        """Test password hashing"""
        from src.services.auth_service import hash_password
        
        hashed = hash_password("test-password")
        assert hashed is not None
        assert hashed != "test-password"
        assert len(hashed) > 0
    
    def test_verify_password(self):
        """Test password verification"""
        from src.services.auth_service import hash_password, verify_password
        
        password = "test-password"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("wrong-password", hashed) is False
    
    def test_create_jwt_token(self):
        """Test JWT token creation"""
        from src.services.auth_service import create_jwt_token
        
        user_data = {
            "user_id": "123",
            "username": "testuser",
            "roles": ["user"],
            "groups": ["group1"]
        }
        
        result = create_jwt_token(user_data)
        assert "token" in result
        assert "expires_at" in result
        assert "jti" in result
        
        # Verify token can be decoded
        token = result["token"]
        # Use the actual JWT_SECRET from the module or decode without verification
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert decoded["user_id"] == "123"
        assert decoded["username"] == "testuser"
    
    @patch('src.services.auth_service.get_user_by_username')
    @patch('src.services.auth_service.dynamodb')
    def test_create_user_success(self, mock_dynamodb, mock_get_user):
        """Test creating a user successfully"""
        from src.services.auth_service import create_user, UserRegistration
        
        mock_get_user.return_value = None  # User doesn't exist
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        user_data = UserRegistration(
            username="testuser",
            password="password123",
            roles=["user"]
        )
        result = create_user(user_data)
        assert result is not None
        assert result["username"] == "testuser"
    
    @patch('src.services.auth_service.get_user_by_username')
    def test_create_user_already_exists(self, mock_get_user):
        """Test creating a user that already exists"""
        from src.services.auth_service import create_user, UserRegistration
        from fastapi import HTTPException
        
        mock_get_user.return_value = {"username": "testuser"}  # User exists
        
        user_data = UserRegistration(
            username="testuser",
            password="password123"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            create_user(user_data)
        assert exc_info.value.status_code == 409
    
    @patch('src.services.auth_service.dynamodb')
    def test_get_user_by_username(self, mock_dynamodb):
        """Test getting user by username"""
        from src.services.auth_service import get_user_by_username
        
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.query.return_value = {
            "Items": [{
                "user_id": "123",
                "username": "testuser",
                "password_hash": "hashed",
                "roles": ["user"]
            }]
        }
        
        result = get_user_by_username("testuser")
        assert result is not None
        assert result["username"] == "testuser"
    
    @patch('src.services.auth_service.dynamodb')
    def test_get_user_by_username_not_found(self, mock_dynamodb):
        """Test getting non-existent user"""
        from src.services.auth_service import get_user_by_username
        
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.query.return_value = {"Items": []}
        mock_table.scan.return_value = {"Items": []}
        
        result = get_user_by_username("nonexistent")
        assert result is None
    
    @patch('src.services.auth_service.get_user_by_username')
    @patch('src.services.auth_service.verify_password')
    def test_authenticate_user_success(self, mock_verify, mock_get_user):
        """Test authenticating a user successfully"""
        from src.services.auth_service import authenticate_user
        
        mock_verify.return_value = True
        mock_get_user.return_value = {
            "user_id": "123",
            "username": "testuser",
            "password_hash": "hashed",
            "roles": ["user"],
            "groups": ["group1"]
        }
        
        result = authenticate_user("testuser", "password123")
        assert result is not None
        assert result["username"] == "testuser"
    
    @patch('src.services.auth_service.get_user_by_username')
    @patch('src.services.auth_service.verify_password')
    def test_authenticate_user_wrong_password(self, mock_verify, mock_get_user):
        """Test authenticating with wrong password"""
        from src.services.auth_service import authenticate_user
        
        mock_verify.return_value = False
        mock_get_user.return_value = {
            "user_id": "123",
            "username": "testuser",
            "password_hash": "hashed"
        }
        
        result = authenticate_user("testuser", "wrong-password")
        assert result is None
    
    @patch('src.services.auth_service.get_user_by_username')
    def test_authenticate_user_not_found(self, mock_get_user):
        """Test authenticating with non-existent user"""
        from src.services.auth_service import authenticate_user
        
        mock_get_user.return_value = None
        
        result = authenticate_user("nonexistent", "password")
        assert result is None
    
    @patch('src.services.auth_service.dynamodb')
    def test_store_token(self, mock_dynamodb):
        """Test storing a token"""
        from src.services.auth_service import store_token
        
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        token_id = "token123"
        user_data = {
            "user_id": "123",
            "username": "testuser",
            "roles": ["user"],
            "groups": ["group1"]
        }
        token = "jwt-token"
        expires_at = datetime.now(timezone.utc)
        
        store_token(token_id, user_data, token, expires_at)
        mock_table.put_item.assert_called_once()
    
    def test_verify_jwt_token_valid(self):
        """Test verifying a valid JWT token"""
        import src.services.auth_service as auth_module
        from src.services.auth_service import verify_jwt_token
        
        # Get the actual secret from the module
        secret = auth_module.JWT_SECRET
        
        # Create a valid token
        payload = {
            "user_id": "123",
            "username": "testuser",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        result = verify_jwt_token(token)
        assert result is not None
        assert result["user_id"] == "123"
    
    def test_verify_jwt_token_expired(self):
        """Test verifying an expired JWT token"""
        import src.services.auth_service as auth_module
        from src.services.auth_service import verify_jwt_token
        
        # Get the actual secret from the module
        secret = auth_module.JWT_SECRET
        
        # Create an expired token
        payload = {
            "user_id": "123",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        result = verify_jwt_token(token)
        assert result is None

