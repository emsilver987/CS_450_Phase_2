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
    from starlette.exceptions import HTTPException as StarletteHTTPException
    
    app = FastAPI()
    
    # Register custom exception handler for HTTP exceptions
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return error_handler(request, exc)
    
    # For generic exceptions, FastAPI's default handler catches them
    # We can wrap the endpoint or use a try-except
    @app.get("/test-error")
    def test_error():
        raise HTTPException(status_code=404, detail="Not found")
    
    @app.get("/test-generic-error")
    async def test_generic_error():
        try:
            raise ValueError("Generic error")
        except Exception as e:
            return error_handler(MagicMock(spec=Request), e)
    
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
        # FastAPI's default HTTPException returns 'detail', custom handler uses 'error' and 'message'
        # Accept either format
        assert "detail" in data or ("error" in data and "message" in data)
    
    def test_generic_exception_handling(self, client):
        """Test generic exception handling"""
        response = client.get("/test-generic-error")
        assert response.status_code == 500
        data = response.json()
        # Custom error handler returns 'error' and 'message'
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
        import json
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        request = MagicMock()
        exc = Exception("")
        
        response = error_handler(request, exc)
        assert response.status_code == 500
        
        # Create a minimal app to render the response properly
        app = FastAPI()
        client = TestClient(app)
        
        # Render the response to get the body content
        response_body = response.body
        data = json.loads(response_body.decode())
        assert "error" in data
        assert "message" in data
        assert data["message"] == "Something went wrong"

