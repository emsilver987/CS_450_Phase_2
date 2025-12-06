"""
Tests for Artifacts Rating endpoints/features
"""
import pytest
import threading
import time
from unittest.mock import patch, MagicMock
from tests.unit.test_index_shared import (
    client, mock_auth, mock_s3_service, mock_artifact_storage,
    reset_rating_state, TEST_MODEL_ID, TEST_MODEL_NAME,
    TEST_DATASET_ID, TEST_DATASET_NAME, TEST_CODE_ID, TEST_CODE_NAME,
    RATING_STATUS_PENDING, RATING_STATUS_COMPLETED, RATING_STATUS_FAILED,
    RATING_STATUS_DISQUALIFIED
)


class TestGetModelRate:
    """Tests for GET /artifact/model/{id}/rate"""

    def test_get_rate_invalid_id(self, mock_auth):
        response = client.get("/artifact/model/{id}/rate")
        # May return 400 (bad request) or 404 (not found)
        assert response.status_code in [400, 404], (
            f"Expected 400 or 404, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "detail" in data

    def test_get_rate_not_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_models", return_value={"models": []}):
                        with patch("src.index.s3") as mock_s3:
                            mock_s3.head_object.side_effect = Exception("Not found")
                            response = client.get("/artifact/model/nonexistent/rate")
                            assert response.status_code == 404

    def test_get_rate_success(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.analyze_model_content") as mock_analyze:
                mock_get.return_value = {
                    "type": "model",
                    "id": "test-id",
                    "name": "test-model"
                }
                mock_analyze.return_value = {
                    "net_score": 0.8,
                    "ramp_up": 0.7,
                    "bus_factor": 0.9,
                    "performance_claims": 0.6,
                    "license": 0.5,
                    "dataset_code": 0.8,
                    "dataset_quality": 0.7,
                    "code_quality": 0.9,
                    "reproducibility": 0.8,
                    "reviewedness": 0.7,
                    "treescore": 0.6,
                    "size_score": {
                        "raspberry_pi": 0.5,
                        "jetson_nano": 0.6,
                        "desktop_pc": 0.7,
                        "aws_server": 0.8
                    }
                }
                response = client.get("/artifact/model/test-id/rate")
                assert response.status_code == 200
                data = response.json()
                assert "net_score" in data
                assert data["net_score"] == 0.8

    def test_get_rate_cached(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._rating_status", {TEST_MODEL_ID: RATING_STATUS_COMPLETED}):
                with patch("src.index._rating_results", {TEST_MODEL_ID: {"net_score": 0.9}}):
                    mock_get.return_value = {
                        "type": "model",
                        "id": "test-id",
                        "name": "test-model"
                    }
                    response = client.get("/artifact/model/test-id/rate")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["net_score"] == 0.9



class TestGetPackageRate:
    """Test get_package_rate function"""

    def test_get_package_rate_success(self, mock_auth):
        """Test successful rate retrieval"""
        with patch("src.index.analyze_model_content") as mock_analyze:
            mock_analyze.return_value = {"score": 0.8}
            with patch("src.index.get_generic_artifact_metadata", return_value={"type": "model", "name": "test-model"}):
                with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                    response = client.get("/artifact/model/test-id/rate")
                    assert response.status_code == 200



class TestRunAsyncRating:
    """Test async rating execution"""
    
    @patch("src.index.analyze_model_content")
    def test_run_async_rating_success(self, mock_analyze):
        """Test _run_async_rating completes successfully"""
        from src.index import (
            _run_async_rating, 
            _rating_status, 
            _rating_results,
            _rating_locks,
            _rating_start_times,
            _rating_lock
        )
        
        mock_analyze.return_value = {"net_score": 0.8}
        
        artifact_id = "test-id-async-success"
        with _rating_lock:
            _rating_status[artifact_id] = "pending"
            _rating_locks[artifact_id] = threading.Event()
            _rating_start_times[artifact_id] = time.time()
        
        _run_async_rating(artifact_id, "test-model", "main")
        
        assert _rating_status[artifact_id] == "completed"
        assert artifact_id in _rating_results
    
    @patch("src.index.analyze_model_content")
    def test_run_async_rating_disqualified(self, mock_analyze):
        """Test _run_async_rating marks model as disqualified"""
        from src.index import (
            _run_async_rating, 
            _rating_status,
            _rating_locks,
            _rating_start_times,
            _rating_lock
        )
        
        mock_analyze.return_value = {"net_score": 0.3}  # Below 0.5 threshold
        
        artifact_id = "test-id-async-disqualified"
        with _rating_lock:
            _rating_status[artifact_id] = "pending"
            _rating_locks[artifact_id] = threading.Event()
            _rating_start_times[artifact_id] = time.time()
        
        _run_async_rating(artifact_id, "test-model", "main")
        
        assert _rating_status[artifact_id] == "disqualified"
    
    @patch("src.index.analyze_model_content")
    def test_run_async_rating_failure(self, mock_analyze):
        """Test _run_async_rating handles exceptions"""
        from src.index import (
            _run_async_rating, 
            _rating_status,
            _rating_locks,
            _rating_start_times,
            _rating_lock
        )
        
        mock_analyze.side_effect = Exception("Rating failed")
        
        artifact_id = "test-id-async-failure"
        with _rating_lock:
            _rating_status[artifact_id] = "pending"
            _rating_locks[artifact_id] = threading.Event()
            _rating_start_times[artifact_id] = time.time()
        
        _run_async_rating(artifact_id, "test-model", "main")
        
        assert _rating_status[artifact_id] == "failed"
    
    @patch("src.index.analyze_model_content")
    def test_run_async_rating_none_result(self, mock_analyze):
        """Test _run_async_rating handles None result"""
        from src.index import (
            _run_async_rating, 
            _rating_status,
            _rating_locks,
            _rating_start_times,
            _rating_lock
        )
        
        mock_analyze.return_value = None
        
        artifact_id = "test-id-async-none"
        with _rating_lock:
            _rating_status[artifact_id] = "pending"
            _rating_locks[artifact_id] = threading.Event()
            _rating_start_times[artifact_id] = time.time()
        
        _run_async_rating(artifact_id, "test-model", "main")
        
        assert _rating_status[artifact_id] == "failed"



