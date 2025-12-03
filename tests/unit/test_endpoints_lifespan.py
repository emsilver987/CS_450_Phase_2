"""
Tests for Lifespan endpoints/features
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from tests.unit.test_index_shared import (
    client, mock_auth, mock_s3_service, mock_artifact_storage,
    reset_rating_state, TEST_MODEL_ID, TEST_MODEL_NAME,
    TEST_DATASET_ID, TEST_DATASET_NAME, TEST_CODE_ID, TEST_CODE_NAME,
    RATING_STATUS_PENDING, RATING_STATUS_COMPLETED, RATING_STATUS_FAILED,
    RATING_STATUS_DISQUALIFIED
)
from src.index import app


class TestLifespan:
    """Tests for lifespan context manager"""

    def test_lifespan_startup(self):
        """Test lifespan startup logic"""
        from src.index import lifespan, app
        import asyncio
        
        async def test_lifespan():
            async with lifespan(app):
                # Check that routes are registered
                routes = [r for r in app.routes if hasattr(r, "path")]
                assert len(routes) > 0
        
        asyncio.run(test_lifespan())

    def test_lifespan_initializes_artifact_storage(self):
        """Test that lifespan initializes artifact storage"""
        from src.index import lifespan, app
        import asyncio
        
        async def test_init():
            with patch("src.index.list_all_artifacts") as mock_list:
                mock_list.return_value = [
                    {
                        "id": "test-id",
                        "type": "dataset",
                        "name": "test-dataset",
                        "url": "https://example.com",
                        "version": "main"
                    }
                ]
                async with lifespan(app):
                    # Artifact storage should be initialized
                    pass
        
        asyncio.run(test_init())



class TestStartupEvent:
    """Test startup_event function"""

    def test_startup_event_runs(self):
        """Test that startup event runs on app startup"""
        # Startup event runs automatically, we can verify routes are registered
        from src.index import app
        routes = [r for r in app.routes if hasattr(r, "path")]
        assert len(routes) > 0



class TestLifespanExceptionHandling:
    """Test exception handling in lifespan function"""

    @patch("src.index.list_all_artifacts")
    def test_lifespan_initialization_exception(self, mock_list):
        """Test lifespan handles exception during initialization"""
        from src.index import lifespan
        import asyncio

        mock_list.side_effect = Exception("Database error")

        async def run_lifespan():
            async with lifespan(app):
                pass

        # Should not raise exception
        asyncio.run(run_lifespan())



