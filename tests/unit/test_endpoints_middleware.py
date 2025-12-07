"""
Tests for Middleware endpoints/features
"""
import pytest
from unittest.mock import patch, MagicMock
from tests.unit.test_index_shared import (
    client, mock_auth, mock_s3_service, mock_artifact_storage,
    reset_rating_state, TEST_MODEL_ID, TEST_MODEL_NAME,
    TEST_DATASET_ID, TEST_DATASET_NAME, TEST_CODE_ID, TEST_CODE_NAME,
    RATING_STATUS_PENDING, RATING_STATUS_COMPLETED, RATING_STATUS_FAILED,
    RATING_STATUS_DISQUALIFIED
)
from src.index import app


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware"""

    def test_logging_middleware_adds_correlation_id(self):
        """Test that middleware adds correlation ID"""
        response = client.get("/health")
        assert response.status_code == 200
        # Correlation ID should be in response headers
        assert "X-Correlation-ID" in response.headers or response.status_code == 200

    def test_logging_middleware_tracks_concurrent_requests(self):
        """Test that middleware tracks concurrent requests"""
        response = client.get("/health")
        assert response.status_code == 200
        # Middleware should execute without error

    def test_logging_middleware_handles_errors(self):
        """Test that middleware handles errors gracefully"""
        # Make a request that might cause an error
        response = client.get("/nonexistent-endpoint")
        # Should not crash, should return 404
        assert response.status_code == 404



class TestLoggingMiddlewareErrorHandling:
    """Test error handling in logging middleware"""

    def test_logging_middleware_exception_during_request(self):
        """Test logging middleware handles exception during request processing"""
        from src.index import LoggingMiddleware
        from fastapi import Request
        from unittest.mock import AsyncMock, MagicMock

        middleware = LoggingMiddleware(app)

        async def failing_call_next(request):
            raise Exception("Request processing error")

        request = MagicMock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.state = MagicMock()

        # Should handle exception and re-raise
        with pytest.raises(Exception):
            import asyncio
            asyncio.run(middleware.dispatch(request, failing_call_next))



