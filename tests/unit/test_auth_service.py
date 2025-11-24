import pytest
from unittest.mock import MagicMock, patch
from src.services.auth_service import (
    hash_password, verify_password, create_jwt_token, verify_jwt_token,
    auth_public, auth_private, UserRegistration, UserLogin
)
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Setup app for testing routers
app = FastAPI()
app.include_router(auth_public)
app.include_router(auth_private)

client = TestClient(app)

def test_password_hashing():
    pwd = "password123"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False

def test_jwt_token_creation_and_verification():
    user_data = {
        "user_id": "123",
        "username": "testuser",
        "roles": ["admin"],
        "groups": ["group1"]
    }
    token_data = create_jwt_token(user_data)
    assert "token" in token_data
    assert "jti" in token_data
    
    decoded = verify_jwt_token(token_data["token"])
    assert decoded is not None
    assert decoded["user_id"] == "123"
    assert decoded["username"] == "testuser"

@patch("src.services.auth_service.dynamodb")
def test_register_user(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.query.return_value = {"Items": []} # No existing user
    mock_table.scan.return_value = {"Items": []}
    
    response = client.post("/auth/register", json={
        "username": "newuser",
        "password": "password123",
        "roles": ["user"]
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    mock_table.put_item.assert_called()

@patch("src.services.auth_service.dynamodb")
def test_login_user(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    # Mock user retrieval
    hashed = hash_password("password123")
    mock_table.query.return_value = {
        "Items": [{
            "user_id": "123",
            "username": "testuser",
            "password_hash": hashed,
            "roles": ["user"]
        }]
    }
    
    response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "password123"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    mock_table.put_item.assert_called() # Storing token

@patch("src.services.auth_service.dynamodb")
def test_login_invalid_credentials(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    # Mock user retrieval
    hashed = hash_password("password123")
    mock_table.query.return_value = {
        "Items": [{
            "user_id": "123",
            "username": "testuser",
            "password_hash": hashed,
            "roles": ["user"]
        }]
    }
    
    response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401
