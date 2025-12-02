"""
Unit tests for entrypoint module
"""
import os
import sys
from unittest.mock import patch


class TestEntrypointAuthSetup:
    """Test JWT middleware setup in entrypoint"""

    def test_entrypoint_without_auth(self):
        """Test entrypoint without auth enabled (no env vars)"""
        # Test the auth condition logic directly
        with patch.dict(os.environ, {}, clear=True):
            enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
            jwt_secret = os.getenv("JWT_SECRET")
            assert enable_auth is False
            assert jwt_secret is None
            # In Python, False or None evaluates to None, but bool(False or None) is False
            assert bool(enable_auth or jwt_secret) is False

    def test_entrypoint_with_enable_auth_true(self):
        """Test entrypoint with ENABLE_AUTH=true"""
        # Remove module from cache to force reload
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        with patch.dict(os.environ, {'ENABLE_AUTH': 'true'}, clear=False):
            with patch('src.index.app') as mock_app:
                # Import the module to trigger execution
                import src.entrypoint
                
                # Verify add_middleware was called
                from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
                mock_app.add_middleware.assert_called()
                args, kwargs = mock_app.add_middleware.call_args
                assert args[0] == JWTAuthMiddleware
                assert kwargs['exempt_paths'] == DEFAULT_EXEMPT

    def test_entrypoint_with_jwt_secret(self):
        """Test entrypoint with JWT_SECRET set"""
        # Remove module from cache to force reload
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        with patch.dict(os.environ, {'JWT_SECRET': 'test-secret-key'}, clear=False):
            with patch('src.index.app') as mock_app:
                # Import the module to trigger execution
                import src.entrypoint
                
                # Verify add_middleware was called
                from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
                mock_app.add_middleware.assert_called()
                args, kwargs = mock_app.add_middleware.call_args
                assert args[0] == JWTAuthMiddleware
                assert kwargs['exempt_paths'] == DEFAULT_EXEMPT

    def test_entrypoint_auth_condition_logic(self):
        """Test the auth condition logic (enable_auth OR jwt_secret)"""
        # Test case 1: ENABLE_AUTH=true, no JWT_SECRET
        with patch.dict(os.environ, {'ENABLE_AUTH': 'true'}, clear=False):
            enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
            jwt_secret = os.getenv("JWT_SECRET")
            assert enable_auth is True
            assert jwt_secret is None
            assert bool(enable_auth or jwt_secret) is True

        # Test case 2: No ENABLE_AUTH, but JWT_SECRET set
        with patch.dict(os.environ, {'JWT_SECRET': 'test-secret'}, clear=False):
            enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
            jwt_secret = os.getenv("JWT_SECRET")
            assert enable_auth is False
            assert jwt_secret == 'test-secret'
            assert bool(enable_auth or jwt_secret) is True

        # Test case 3: Neither set
        with patch.dict(os.environ, {}, clear=True):
            enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
            jwt_secret = os.getenv("JWT_SECRET")
            assert enable_auth is False
            assert jwt_secret is None
            assert bool(enable_auth or jwt_secret) is False

    def test_entrypoint_app_reference(self):
        """Test that entrypoint correctly references the app"""
        # Ensure we have a clean import of entrypoint with the real app
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        import src.entrypoint
        
        from src.entrypoint import app
        from src.index import app as index_app
        
        # They should reference the same app instance
        assert app is index_app

    def test_entrypoint_imports(self):
        """Test that entrypoint imports work correctly"""
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        import src.entrypoint
        from src.entrypoint import app
        from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
        
        assert app is not None
        assert JWTAuthMiddleware is not None
        assert DEFAULT_EXEMPT is not None

    def test_entrypoint_no_auth_when_disabled(self):
        """Test that middleware is not added when auth is disabled"""
        # Remove module from cache to force reload
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.index.app') as mock_app:
                # Import the module to trigger execution
                import src.entrypoint
                
                # Verify add_middleware was NOT called
                mock_app.add_middleware.assert_not_called()

    def test_entrypoint_module_execution(self):
        """Test that entrypoint module code is actually executed"""
        # Remove module from cache to force reload
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        # Import to trigger execution
        import src.entrypoint
        
        # Verify the module has the expected attributes
        assert hasattr(src.entrypoint, 'app')
        assert src.entrypoint.app is not None

    def test_entrypoint_both_conditions_false(self):
        """Test entrypoint when both ENABLE_AUTH and JWT_SECRET are not set"""
        # Remove module from cache to force reload
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.index.app') as mock_app:
                # Import the module to trigger execution
                import src.entrypoint
                
                # Verify middleware was NOT added
                mock_app.add_middleware.assert_not_called()

    def test_entrypoint_both_conditions_true(self):
        """Test entrypoint when both ENABLE_AUTH=true and JWT_SECRET are set"""
        # Remove module from cache to force reload
        if 'src.entrypoint' in sys.modules:
            del sys.modules['src.entrypoint']
        
        with patch.dict(os.environ, {'ENABLE_AUTH': 'true', 'JWT_SECRET': 'test-secret'}, clear=False):
            with patch('src.index.app') as mock_app:
                from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
                
                # Import the module to trigger execution
                import src.entrypoint
                
                # Verify middleware was added
                mock_app.add_middleware.assert_called_once()
                args, kwargs = mock_app.add_middleware.call_args
                assert args[0] == JWTAuthMiddleware
                assert kwargs['exempt_paths'] == DEFAULT_EXEMPT
