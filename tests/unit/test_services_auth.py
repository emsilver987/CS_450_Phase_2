"""
Unit tests for auth_service
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import jwt


class TestAuthService:
    """Test authentication service"""
    
    @patch('src.services.auth_service.get_users_table')
    def test_hash_password(self, mock_table):
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
        assert "remaining_uses" in result
        
        # Verify token can be decoded
        token = result["token"]
        decoded = jwt.decode(token, "test-secret", algorithms=["HS256"], options={"verify_signature": False})
        assert decoded["user_id"] == "123"
        assert decoded["username"] == "testuser"
    
    @patch('src.services.auth_service.get_users_table')
    def test_create_user_success(self, mock_table):
        """Test creating a user successfully"""
        from src.services.auth_service import create_user
        
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {}  # User doesn't exist
        
        result = create_user("testuser", "password123", roles=["user"])
        assert result is not None
        assert result["username"] == "testuser"
    
    @patch('src.services.auth_service.get_users_table')
    def test_create_user_already_exists(self, mock_table):
        """Test creating a user that already exists"""
        from src.services.auth_service import create_user
        
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {
            "Item": {"username": "testuser"}
        }
        
        result = create_user("testuser", "password123")
        assert result is None
    
    @patch('src.services.auth_service.get_users_table')
    def test_get_user_by_username(self, mock_table):
        """Test getting user by username"""
        from src.services.auth_service import get_user_by_username
        
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {
            "Item": {
                "user_id": "123",
                "username": "testuser",
                "password_hash": "hashed",
                "roles": ["user"]
            }
        }
        
        result = get_user_by_username("testuser")
        assert result is not None
        assert result["username"] == "testuser"
    
    @patch('src.services.auth_service.get_users_table')
    def test_get_user_by_username_not_found(self, mock_table):
        """Test getting non-existent user"""
        from src.services.auth_service import get_user_by_username
        
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {}
        
        result = get_user_by_username("nonexistent")
        assert result is None
    
    @patch('src.services.auth_service.get_users_table')
    @patch('src.services.auth_service.verify_password')
    def test_authenticate_user_success(self, mock_verify, mock_table):
        """Test authenticating a user successfully"""
        from src.services.auth_service import authenticate_user
        
        mock_verify.return_value = True
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {
            "Item": {
                "user_id": "123",
                "username": "testuser",
                "password_hash": "hashed",
                "roles": ["user"],
                "groups": ["group1"]
            }
        }
        
        result = authenticate_user("testuser", "password123")
        assert result is not None
        assert result["username"] == "testuser"
    
    @patch('src.services.auth_service.get_users_table')
    @patch('src.services.auth_service.verify_password')
    def test_authenticate_user_wrong_password(self, mock_verify, mock_table):
        """Test authenticating with wrong password"""
        from src.services.auth_service import authenticate_user
        
        mock_verify.return_value = False
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {
            "Item": {
                "user_id": "123",
                "username": "testuser",
                "password_hash": "hashed"
            }
        }
        
        result = authenticate_user("testuser", "wrong-password")
        assert result is None
    
    @patch('src.services.auth_service.get_tokens_table')
    def test_store_token(self, mock_table):
        """Test storing a token"""
        from src.services.auth_service import store_token
        
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        
        token_data = {
            "token_id": "token123",
            "user_id": "123",
            "token": "jwt-token",
            "expires_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = store_token(token_data)
        assert result is True
        mock_table_instance.put_item.assert_called_once()
    
    @patch('src.services.auth_service.get_tokens_table')
    def test_verify_jwt_token_valid(self, mock_table):
        """Test verifying a valid JWT token"""
        from src.services.auth_service import verify_jwt_token
        
        # Create a valid token
        secret = "test-secret"
        payload = {
            "user_id": "123",
            "username": "testuser",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance
        mock_table_instance.get_item.return_value = {
            "Item": {
                "token_id": "token123",
                "user_id": "123",
                "remaining_uses": 10
            }
        }
        
        with patch('src.services.auth_service.JWT_SECRET', secret):
            result = verify_jwt_token(token)
            assert result is not None
            assert result["user_id"] == "123"
    
    @patch('src.services.auth_service.get_tokens_table')
    def test_verify_jwt_token_expired(self, mock_table):
        """Test verifying an expired JWT token"""
        from src.services.auth_service import verify_jwt_token
        
        # Create an expired token
        secret = "test-secret"
        payload = {
            "user_id": "123",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        with patch('src.services.auth_service.JWT_SECRET', secret):
            result = verify_jwt_token(token)
            assert result is None

