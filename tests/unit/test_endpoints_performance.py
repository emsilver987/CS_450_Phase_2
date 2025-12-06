"""
Tests for Performance endpoints/features
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
from unittest.mock import patch, MagicMock


class TestPerformanceEndpoints:
    """Tests for performance workload endpoints"""

    def test_trigger_performance_workload_no_auth(self):
        """Test trigger workload - endpoint doesn't require auth"""
        # Performance endpoint doesn't require auth, so it should work without auth token
        with patch("src.services.performance.workload_trigger.trigger_workload") as mock_trigger:
            mock_trigger.return_value = {"run_id": "test-run", "status": "started"}
            response = client.post("/health/performance/workload", json={
                "num_clients": 10,
                "model_id": "test-model"
            })
            # Should succeed (202) or fail with 400/500, but not 403
            assert response.status_code != 403

    def test_trigger_performance_workload_success(self, mock_auth):
        """Test successful workload trigger"""
        with patch("src.services.performance.workload_trigger.trigger_workload") as mock_trigger:
            mock_trigger.return_value = {"run_id": "test-run-123", "status": "started"}
            response = client.post(
                "/health/performance/workload",
                json={
                    "num_clients": 10,
                    "model_id": "test-model",
                    "duration_seconds": 60
                }
            )
            assert response.status_code == 202
            data = response.json()
            assert "run_id" in data

    def test_trigger_performance_workload_invalid_params(self, mock_auth):
        """Test workload trigger with invalid parameters"""
        # Invalid num_clients
        response = client.post(
            "/health/performance/workload",
            json={"num_clients": -1, "model_id": "test"}
        )
        assert response.status_code == 400

        # Invalid model_id
        response = client.post(
            "/health/performance/workload",
            json={"num_clients": 10, "model_id": ""}
        )
        assert response.status_code == 400

        # Invalid duration
        response = client.post(
            "/health/performance/workload",
            json={"num_clients": 10, "model_id": "test", "duration_seconds": 0}
        )
        assert response.status_code == 400

    def test_get_performance_results_success(self, mock_auth):
        """Test get performance results"""
        with patch("src.services.performance.results_retrieval.get_performance_results") as mock_get_results:
            with patch("src.services.performance.workload_trigger.get_workload_status") as mock_status:
                mock_status.return_value = {"status": "completed"}
                mock_get_results.return_value = {
                    "status": "completed",
                    "metrics": {"total_requests": 100}
                }
                response = client.get("/health/performance/results/test-run-123")
                assert response.status_code == 200
                data = response.json()
                assert "status" in data

    def test_get_performance_results_not_found(self, mock_auth):
        """Test get performance results when not found"""
        with patch("src.services.performance.results_retrieval.get_performance_results") as mock_get_results:
            with patch("src.services.performance.workload_trigger.get_workload_status") as mock_status:
                mock_status.return_value = None
                mock_get_results.return_value = {
                    "status": "not_found",
                    "metrics": {"total_requests": 0}
                }
                response = client.get("/health/performance/results/nonexistent")
                assert response.status_code == 404



