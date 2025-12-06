"""
Unit tests for error handler middleware
"""
import pytest
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from src.middleware.errorHandler import error_handler


class TestErrorHandler:
    """Test error handler middleware"""
    
    def test_error_handler_with_http_exception(self):
        """Test error handler with HTTPException"""
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        exc = HTTPException(status_code=404, detail="Not found")
        
        response = error_handler(request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        data = response.body.decode()
        assert "error" in data
        assert "HTTPException" in data or "404" in data
    
    def test_error_handler_with_generic_exception(self):
        """Test error handler with generic exception"""
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        exc = ValueError("Something went wrong")
        
        response = error_handler(request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        data = response.body.decode()
        assert "error" in data
        assert "ValueError" in data
    
    def test_error_handler_with_exception_with_status_code(self):
        """Test error handler with exception that has status_code attribute"""
        class CustomException(Exception):
            def __init__(self, status_code):
                self.status_code = status_code
                super().__init__("Custom error")
        
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        exc = CustomException(403)
        
        response = error_handler(request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 403
    
    def test_error_handler_with_exception_with_status_attribute(self):
        """Test error handler with exception that has status attribute"""
        class CustomException(Exception):
            def __init__(self, status):
                self.status = status
                super().__init__("Custom error")
        
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        exc = CustomException(401)
        
        response = error_handler(request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
    
    def test_error_handler_with_empty_message(self):
        """Test error handler with exception that has empty message"""
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        exc = Exception()
        
        response = error_handler(request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        data = response.body.decode()
        assert "Something went wrong" in data or "error" in data

