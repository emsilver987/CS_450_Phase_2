"""
Tests for Health endpoints/features
"""
import pytest
from unittest.mock import patch, MagicMock
from tests.unit.test_index_shared import (
    client, mock_auth, mock_s3_service, mock_artifact_storage,
    reset_rating_state, TEST_MODEL_ID, TEST_MODEL_NAME
)


class TestHealthComponents:
    """Additional tests for health components endpoint"""

    def test_health_components_performance_metrics(self):
        """Test health components with performance metrics"""
        with patch("src.services.performance.workload_trigger.get_latest_workload_metrics") as mock_metrics:
            mock_metrics.return_value = {"status": "ok", "runs": 5}
            response = client.get("/health/components?windowMinutes=60")
            assert response.status_code == 200
            data = response.json()
            assert "components" in data
            # Should have performance component
            perf_component = next((c for c in data["components"] if c["id"] == "performance"), None)
            assert perf_component is not None

    def test_health_components_performance_unavailable(self):
        """Test health components when performance module unavailable"""
        with patch("src.services.performance.workload_trigger.get_latest_workload_metrics", side_effect=Exception("Module unavailable")):
            response = client.get("/health/components?windowMinutes=60")
            assert response.status_code == 200
            data = response.json()
            # Should still return components with performance marked as unknown
            perf_component = next((c for c in data["components"] if c["id"] == "performance"), None)
            assert perf_component is not None
            assert perf_component["status"] == "unknown"



def test_health_components():
    """Test health components endpoint returns valid component list"""
    response = client.get("/health/components")
    assert response.status_code == 200
    data = response.json()
    assert "components" in data
    assert data["components"][0]["id"] == "validator-service"


def test_health_components_invalid_window():
    """Test health components with invalid window (below minimum) returns 400"""
    response = client.get("/health/components?windowMinutes=1")
    assert response.status_code == 400




