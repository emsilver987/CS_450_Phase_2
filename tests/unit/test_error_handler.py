"""
Tests for errorHandler.py middleware
"""
import pytest
from unittest.mock import MagicMock
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.middleware.errorHandler import error_handler


@pytest.fixture
def app():
    """Create test app with error handler"""
    app = FastAPI()
    
    @app.exception_handler(Exception)
    async def custom_handler(request: Request, exc: Exception):
        return error_handler(request, exc)
    
    @app.get("/test-error")
    def test_error():
        raise HTTPException(status_code=404, detail="Not found")
    
    @app.get("/test-generic-error")
    def test_generic_error():
        raise ValueError("Generic error")
    
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestErrorHandler:
    """Test error handler middleware"""
    
    def test_http_exception_handling(self, client):
        """Test HTTPException handling"""
        response = client.get("/test-error")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "message" in data
    
    def test_generic_exception_handling(self, client):
        """Test generic exception handling"""
        response = client.get("/test-generic-error")
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "message" in data
    
    def test_error_handler_with_status_code(self):
        """Test error handler with status code attribute"""
        class CustomException(Exception):
            status_code = 403
        
        request = MagicMock()
        exc = CustomException("Forbidden")
        
        response = error_handler(request, exc)
        assert response.status_code == 403
    
    def test_error_handler_with_status_attr(self):
        """Test error handler with status attribute"""
        class CustomException(Exception):
            status = 418
        
        request = MagicMock()
        exc = CustomException("Teapot")
        
        response = error_handler(request, exc)
        assert response.status_code == 418
    
    def test_error_handler_default_status(self):
        """Test error handler default status code"""
        request = MagicMock()
        exc = Exception("Generic error")
        
        response = error_handler(request, exc)
        assert response.status_code == 500
    
    def test_error_handler_empty_message(self):
        """Test error handler with empty message"""
        request = MagicMock()
        exc = Exception("")
        
        response = error_handler(request, exc)
        data = response.json()
        assert "message" in data
        assert data["message"] == "Something went wrong"

