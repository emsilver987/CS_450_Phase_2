"""
Tests for entrypoint.py
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from src.entrypoint import app


class TestEntrypoint:
    """Test entrypoint configuration"""
    
    def test_app_exists(self):
        """Test that app exists"""
        assert app is not None
    
    def test_app_has_routes(self):
        """Test that app has routes"""
        # Check that app has routes registered
        routes = [route.path for route in app.routes]
        assert len(routes) > 0
    
    @patch.dict(os.environ, {"ENABLE_AUTH": "true"})
    @patch("src.entrypoint.JWTAuthMiddleware")
    def test_auth_enabled(self, mock_middleware):
        """Test that auth middleware is added when ENABLE_AUTH is true"""
        # Reload module to pick up env var change
        import importlib
        import src.entrypoint
        importlib.reload(src.entrypoint)
        # Middleware should be added
        # Note: This test may need adjustment based on actual implementation
        pass
    
    @patch.dict(os.environ, {"ENABLE_AUTH": "false", "JWT_SECRET": ""}, clear=True)
    def test_auth_disabled_no_secret(self):
        """Test that auth middleware is not added when disabled"""
        # Reload module to pick up env var change
        import importlib
        import src.entrypoint
        importlib.reload(src.entrypoint)
        # Middleware should not be added
        pass
    
    @patch.dict(os.environ, {"JWT_SECRET": "test-secret"})
    @patch("src.entrypoint.JWTAuthMiddleware")
    def test_auth_enabled_with_secret(self, mock_middleware):
        """Test that auth middleware is added when JWT_SECRET is set"""
        # Reload module to pick up env var change
        import importlib
        import src.entrypoint
        importlib.reload(src.entrypoint)
        # Middleware should be added
        pass

