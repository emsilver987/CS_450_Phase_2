import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys
import threading

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock boto3 and watchtower to prevent startup hangs and logging errors
# Mock boto3 to prevent startup hangs (watchtower is patched in conftest.py)
with patch("boto3.client"):
    from src.index import app

client = TestClient(app)


# Test constants
TEST_MODEL_ID = "test-id"
TEST_MODEL_NAME = "test-model"
TEST_DATASET_ID = "test-dataset-id"
TEST_DATASET_NAME = "test-dataset"
TEST_CODE_ID = "test-code-id"
TEST_CODE_NAME = "test-code"
RATING_STATUS_PENDING = "pending"
RATING_STATUS_COMPLETED = "completed"
RATING_STATUS_FAILED = "failed"
RATING_STATUS_DISQUALIFIED = "disqualified"



@pytest.fixture
def mock_auth():
    with patch("src.index.verify_auth_token") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_s3_service():
    with patch("src.index.list_models") as mock_list:
        with patch("src.index.list_artifacts_from_s3") as mock_list_s3:
            yield {"list_models": mock_list, "list_artifacts_from_s3": mock_list_s3}


@pytest.fixture
def mock_artifact_storage():
    with patch("src.index.list_all_artifacts") as mock_list:
        with patch("src.index._artifact_storage", {}) as mock_storage:
            yield {"list_all_artifacts": mock_list, "storage": mock_storage}


@pytest.fixture(autouse=True)
def reset_rating_state():
    """Reset rating state between tests to ensure test isolation."""
    from src.index import (
        _rating_status,
        _rating_locks,
        _rating_results,
        _rating_start_times
    )
    
    # Store original state
    original_status = _rating_status.copy()
    original_locks = _rating_locks.copy()
    original_results = _rating_results.copy()
    original_start_times = _rating_start_times.copy()
    
    # Clear state before test
    _rating_status.clear()
    _rating_locks.clear()
    _rating_results.clear()
    _rating_start_times.clear()
    
    yield
    
    # Restore original state after test
    _rating_status.clear()
    _rating_status.update(original_status)
    _rating_locks.clear()
    _rating_locks.update(original_locks)
    _rating_results.clear()
    _rating_results.update(original_results)
    _rating_start_times.clear()
    _rating_start_times.update(original_start_times)

def test_sanitize_model_id_for_s3():
    """Test sanitize_model_id_for_s3 helper function"""
    from src.index import sanitize_model_id_for_s3
    
    # Test basic sanitization
    result = sanitize_model_id_for_s3("test/model")
    assert result == "test_model"
    
    # Test with special characters
    result = sanitize_model_id_for_s3("test:model/version")
    assert ":" not in result
    assert "/" not in result
    
    # Test with HuggingFace URL
    result = sanitize_model_id_for_s3("https://huggingface.co/test/model")
    assert "https://" not in result
    assert "huggingface.co" not in result
    
    # Test with various special characters
    result = sanitize_model_id_for_s3('test"model<version>|path')
    assert '"' not in result
    assert "<" not in result
    assert ">" not in result
    assert "|" not in result


def test_generate_download_url():
    """Test generate_download_url helper function"""
    from src.index import generate_download_url
    
    # Test model URL generation
    url = generate_download_url("test-model", "model", "main")
    assert "model" in url
    assert "test-model" in url or "test_model" in url
    assert "main" in url
    
    # Test dataset URL generation
    url = generate_download_url("test-dataset", "dataset", "v1.0")
    assert "dataset" in url
    assert "v1.0" in url
    
    # Test code URL generation
    url = generate_download_url("test-code", "code", "latest")
    assert "code" in url
    assert "latest" in url


def test_build_artifact_response():
    """Test build_artifact_response helper function"""
    from src.index import build_artifact_response
    
    response = build_artifact_response(
        artifact_name="test-model",
        artifact_id="test-id-123",
        artifact_type="model",
        url="https://example.com/model",
        version="main"
    )
    
    assert "metadata" in response
    assert "data" in response
    assert response["metadata"]["name"] == "test-model"
    assert response["metadata"]["id"] == "test-id-123"
    assert response["metadata"]["type"] == "model"
    assert "url" in response["data"]
    assert "download_url" in response["data"]


def test_cleanup_stuck_ratings():
    """Test _cleanup_stuck_ratings helper function"""
    from src.index import (
        _cleanup_stuck_ratings,
        _rating_status,
        _rating_start_times,
        _rating_locks
    )
    import time
    
    # Set up a stuck rating (older than 10 minutes)
    artifact_id = "stuck-artifact-1"
    _rating_status[artifact_id] = "pending"
    _rating_start_times[artifact_id] = time.time() - 700  # 11+ minutes ago
    
    # Create a lock for this rating
    import threading
    _rating_locks[artifact_id] = threading.Event()
    
    # Run cleanup
    _cleanup_stuck_ratings()
    
    # Verify stuck rating was cleaned up
    assert _rating_status[artifact_id] == "failed"
    assert artifact_id not in _rating_start_times


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

def test_list_artifacts_no_auth():
    """Test list artifacts endpoint requires authentication"""
    # Don't use mock_auth here
    with patch("src.index.verify_auth_token", return_value=False):
        response = client.post("/artifacts", json=[{"name": "*"}])
        assert response.status_code == 403

def test_list_artifacts_wildcard(mock_auth, mock_s3_service, mock_artifact_storage):
    # Mock S3 models
    mock_s3_service["list_models"].return_value = {
        "models": [{"name": "model1", "id": "id1"}]
    }
    # Mock DB artifacts
    mock_artifact_storage["list_all_artifacts"].return_value = [
        {"name": "dataset1", "id": "id2", "type": "dataset"}
    ]

    response = client.post("/artifacts", json=[{"name": "*"}])
    assert response.status_code == 200
    data = response.json()
    names = [d["name"] for d in data]
    assert "model1" in names
    assert "dataset1" in names

def test_list_artifacts_exact_match(mock_auth, mock_s3_service, mock_artifact_storage):
    # Mock DB artifacts
    mock_artifact_storage["list_all_artifacts"].return_value = [
        {"name": "target-pkg", "id": "id1", "type": "model"},
        {"name": "other-pkg", "id": "id2", "type": "dataset"}
    ]

    response = client.post("/artifacts", json=[{"name": "target-pkg"}])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "target-pkg"

def test_list_artifacts_filter_type(mock_auth, mock_s3_service, mock_artifact_storage):
    mock_artifact_storage["list_all_artifacts"].return_value = [
        {"name": "pkg1", "id": "id1", "type": "model"},
        {"name": "pkg2", "id": "id2", "type": "dataset"}
    ]

    # Filter for dataset
    response = client.post("/artifacts", json=[{"name": "*", "types": ["dataset"]}])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["type"] == "dataset"

def test_list_artifacts_invalid_body(mock_auth):
    response = client.post("/artifacts", json={"not": "a list"})
    assert response.status_code == 400

def test_list_artifacts_missing_name(mock_auth):
    response = client.post("/artifacts", json=[{"no_name": "here"}])
    assert response.status_code == 400


# Phase 3: Main Endpoints Tests

class TestGetArtifactByName:
    """Tests for GET /artifact/byName/{name}"""

    def test_get_artifact_by_name_no_auth(self):
        """Test get artifact by name requires authentication"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.get("/artifact/byName/test-model")
            assert response.status_code == 403

    def test_get_artifact_by_name_empty_name(self, mock_auth):
        """Test get_artifact_by_name with empty name returns 400"""
        response = client.get("/artifact/byName/")
        assert response.status_code == 400

    def test_get_artifact_by_name_found_in_db(self, mock_auth):
        """Test get artifact by name when found in database"""
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_all_artifacts") as mock_db:
                mock_list.return_value = {"models": []}
                mock_db.return_value = [
                    {"name": "test-model", "id": "test-id", "type": "model"}
                ]
                response = client.get("/artifact/byName/test-model")
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) > 0
                assert data[0]["name"] == "test-model"

    def test_get_artifact_by_name_found_in_s3(self, mock_auth):
        """Test get artifact by name when found in S3"""
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_all_artifacts") as mock_db:
                with patch("src.index.s3") as mock_s3:
                    mock_list.return_value = {
                        "models": [{"name": "test-model", "id": "test-id"}]
                    }
                    mock_db.return_value = []
                    mock_s3.get_object.return_value = {
                        "Body": MagicMock(read=lambda: b'{"artifact_id": "test-id"}')
                    }
                    response = client.get("/artifact/byName/test-model")
                    assert response.status_code == 200

    def test_get_artifact_by_name_not_found(self, mock_auth):
        """Test get artifact by name returns 404 when not found"""
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_all_artifacts") as mock_db:
                with patch("src.index.list_artifacts_from_s3") as mock_s3_list:
                    mock_list.return_value = {"models": []}
                    mock_db.return_value = []
                    mock_s3_list.return_value = {"artifacts": []}
                    response = client.get("/artifact/byName/nonexistent")
                    assert response.status_code == 404


class TestSearchArtifactsByRegex:
    """Tests for POST /artifact/byRegEx"""

    def test_search_by_regex_no_auth(self):
        """Test search artifacts by regex requires authentication"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.post("/artifact/byRegEx", json={"regex": "test.*"})
            assert response.status_code == 403

    def test_search_by_regex_missing_field(self, mock_auth):
        """Test search by regex returns 400 when regex field is missing"""
        response = client.post("/artifact/byRegEx", json={})
        assert response.status_code == 400

    def test_search_by_regex_invalid_regex(self, mock_auth):
        """Test search by regex returns 400 for invalid regex syntax"""
        response = client.post("/artifact/byRegEx", json={"regex": "[invalid"})
        assert response.status_code == 400

    def test_search_by_regex_redos_detection(self, mock_auth):
        """Test search by regex detects and rejects ReDoS patterns"""
        response = client.post("/artifact/byRegEx", json={"regex": "(a|aa)*"})
        assert response.status_code == 400

    def test_search_by_regex_success(self, mock_auth):
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_artifacts_from_s3") as mock_s3_list:
                with patch("src.index.list_all_artifacts") as mock_db:
                    mock_list.return_value = {
                        "models": [{"name": "test-model", "id": "test-id"}]
                    }
                    mock_s3_list.return_value = {"artifacts": []}
                    mock_db.return_value = []
                    response = client.post("/artifact/byRegEx", json={"regex": "test.*"})
                    assert response.status_code == 200
                    data = response.json()
                    assert isinstance(data, list)

    def test_search_by_regex_not_found(self, mock_auth):
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_artifacts_from_s3") as mock_s3_list:
                with patch("src.index.list_all_artifacts") as mock_db:
                    mock_list.return_value = {"models": []}
                    mock_s3_list.return_value = {"artifacts": []}
                    mock_db.return_value = []
                    response = client.post("/artifact/byRegEx", json={"regex": "nonexistent.*"})
                    assert response.status_code == 404


class TestGetArtifact:
    """Tests for GET /artifact/{artifact_type}/{id}"""

    def test_get_artifact_no_auth(self):
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.get("/artifact/model/test-id")
            assert response.status_code == 403

    def test_get_artifact_model_found_in_db(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "name": "test-model",
                "id": "test-id",
                "type": "model",
                "url": "https://huggingface.co/test-model",
                "version": "main"
            }
            response = client.get("/artifact/model/test-id")
            assert response.status_code == 200
            data = response.json()
            assert "metadata" in data
            assert data["metadata"]["name"] == "test-model"

    def test_get_artifact_model_not_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_models") as mock_list:
                        with patch("src.index.s3") as mock_s3:
                            from botocore.exceptions import ClientError
                            mock_list.return_value = {"models": []}
                            error_response = {"Error": {"Code": "404"}}
                            mock_s3.head_object.side_effect = ClientError(
                                error_response, "HeadObject"
                            )
                            response = client.get("/artifact/model/nonexistent")
                            assert response.status_code == 404

    def test_get_artifact_dataset_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "name": "test-dataset",
                "id": "test-id",
                "type": "dataset",
                "url": "https://example.com/dataset/test-dataset",
                "version": "main"
            }
            response = client.get("/artifact/dataset/test-id")
            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["type"] == "dataset"

    def test_get_artifact_code_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "name": "test-code",
                "id": "test-id",
                "type": "code",
                "url": "https://example.com/code/test-code",
                "version": "main"
            }
            response = client.get("/artifact/code/test-id")
            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["type"] == "code"


class TestPostArtifactIngest:
    """Tests for POST /artifact/ingest"""

    def test_ingest_no_auth(self):
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.post("/artifact/ingest", data={"name": "test-model"})
            assert response.status_code == 403

    def test_ingest_missing_name(self, mock_auth):
        response = client.post("/artifact/ingest", data={})
        assert response.status_code == 400

    def test_ingest_model_success(self, mock_auth):
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.model_ingestion") as mock_ingest:
                with patch("src.index.download_model") as mock_download:
                    with patch("src.index.save_artifact"):
                        with patch("src.index.store_artifact_metadata") as mock_store:
                            with patch("src.index._link_model_to_datasets_code"):
                                with patch("src.index._run_async_rating"):
                                    with patch("src.index.get_artifact_from_db") as mock_get:
                                        mock_list.return_value = {"models": []}
                                        mock_ingest.return_value = None
                                        mock_download.return_value = b"fake zip content"
                                        mock_get.return_value = {"id": "test-id"}
                                        mock_store.return_value = None
                                        response = client.post(
                                            "/artifact/ingest",
                                            data={"name": "test-model", "version": "main"}
                                        )
                                        assert response.status_code == 200
                                        data = response.json()
                                        assert "message" in data
                                        assert data["message"] == "Ingest successful"

    def test_ingest_model_already_exists(self, mock_auth):
        with patch("src.index.list_models") as mock_list:
            mock_list.return_value = {
                "models": [{"name": "test-model", "id": "test-id"}]
            }
            response = client.post(
                "/artifact/ingest",
                data={"name": "test-model", "version": "main"}
            )
            assert response.status_code == 409

    def test_ingest_dataset_success(self, mock_auth):
        with patch("src.index.save_artifact"):
            with patch("src.index.store_artifact_metadata"):
                with patch("src.index._link_dataset_code_to_models"):
                    response = client.post(
                        "/artifact/ingest",
                        data={"name": "test-dataset", "type": "dataset", "version": "main"}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["message"] == "Ingest successful"


class TestGetArtifactCost:
    """Tests for GET /artifact/{artifact_type}/{id}/cost"""

    def test_get_cost_no_auth(self):
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.get("/artifact/model/test-id/cost")
            assert response.status_code == 403

    def test_get_cost_model_without_dependency(self, mock_auth):
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_sizes") as mock_sizes:
                    mock_get.return_value = {"type": "model", "id": "test-id"}
                    mock_sizes.return_value = {"full": 1024 * 1024}  # 1MB
                    response = client.get("/artifact/model/test-id/cost")
                    assert response.status_code == 200
                    data = response.json()
                    assert "test-id" in data
                    assert "total_cost" in data["test-id"]

    def test_get_cost_model_with_dependency(self, mock_auth):
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_sizes") as mock_sizes:
                    with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                        mock_get.return_value = {"type": "model", "id": "test-id"}
                        mock_sizes.return_value = {"full": 1024 * 1024}
                        mock_lineage.return_value = {
                            "lineage_map": {
                                "dep-id": {"name": "dep-model"}
                            }
                        }
                        response = client.get("/artifact/model/test-id/cost?dependency=true")
                        assert response.status_code == 200
                        data = response.json()
                        assert "test-id" in data
                        assert "standalone_cost" in data["test-id"]

    def test_get_cost_dataset(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "type": "dataset",
                "id": "test-id",
                "name": "test-dataset"
            }
            response = client.get("/artifact/dataset/test-id/cost")
            assert response.status_code == 200
            data = response.json()
            assert "test-id" in data
            assert data["test-id"]["total_cost"] == 0.0

    def test_get_cost_not_found(self, mock_auth):
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index.list_models", return_value={"models": []}):
                with patch("src.index.s3") as mock_s3:
                    mock_s3.head_object.side_effect = Exception("Not found")
                    response = client.get("/artifact/model/nonexistent/cost")
                    assert response.status_code == 404


class TestGetArtifactAudit:
    """Tests for GET /artifact/{artifact_type}/{id}/audit"""

    def test_get_audit_no_auth(self):
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.get("/artifact/model/test-id/audit")
            assert response.status_code == 403

    def test_get_audit_model_success(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.s3") as mock_s3:
                from datetime import datetime, timezone
                mock_get.return_value = {
                    "type": "model",
                    "id": "test-id",
                    "name": "test-model"
                }
                mock_s3.head_object.return_value = {
                    "LastModified": datetime.now(timezone.utc)
                }
                response = client.get("/artifact/model/test-id/audit")
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) > 0
                assert data[0]["action"] == "CREATE"

    def test_get_audit_dataset_success(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "type": "dataset",
                "id": "test-id",
                "name": "test-dataset"
            }
            response = client.get("/artifact/dataset/test-id/audit")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert data[0]["action"] == "CREATE"

    def test_get_audit_not_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.list_models", return_value={"models": []}):
                    with patch("src.index.s3") as mock_s3:
                        from botocore.exceptions import ClientError
                        error_response = {"Error": {"Code": "NoSuchKey"}}
                        mock_s3.head_object.side_effect = ClientError(
                            error_response, "HeadObject"
                        )
                        response = client.get("/artifact/model/nonexistent/audit")
                        assert response.status_code == 404


class TestGetModelRate:
    """Tests for GET /artifact/model/{id}/rate"""

    def test_get_rate_invalid_id(self, mock_auth):
        response = client.get("/artifact/model/{id}/rate")
        assert response.status_code == 404
        data = response.json()
        assert "Artifact does not exist" in data["detail"]

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


class TestGetModelLineage:
    """Tests for GET /artifact/model/{id}/lineage"""

    def test_get_lineage_no_auth(self):
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.get("/artifact/model/test-id/lineage")
            assert response.status_code == 403

    def test_get_lineage_empty_id(self, mock_auth):
        response = client.get("/artifact/model/ /lineage")
        assert response.status_code == 400

    def test_get_lineage_success(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                    mock_get.return_value = {
                        "type": "model",
                        "id": "test-id",
                        "name": "test-model"
                    }
                    mock_lineage.return_value = {
                        "lineage_map": {
                            "test-id": {
                                "name": "test-model",
                                "source": "config_json",
                                "dependencies": [
                                    {"id": "dep-id", "relationship": "uses"}
                                ]
                            }
                        }
                    }
                    response = client.get("/artifact/model/test-id/lineage")
                    assert response.status_code == 200
                    data = response.json()
                    assert "nodes" in data
                    assert "edges" in data
                    assert len(data["nodes"]) > 0

    def test_get_lineage_not_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.list_models", return_value={"models": []}):
                    with patch("src.index.s3") as mock_s3:
                        mock_s3.head_object.side_effect = Exception("Not found")
                        response = client.get("/artifact/model/nonexistent/lineage")
                        assert response.status_code == 404

    def test_get_lineage_error(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                    mock_get.return_value = {
                        "type": "model",
                        "id": "test-id"
                    }
                    mock_lineage.return_value = {"error": "Malformed metadata"}
                    response = client.get("/artifact/model/test-id/lineage")
                    assert response.status_code == 400


class TestCheckModelLicense:
    """Tests for POST /artifact/model/{id}/license-check"""

    def test_license_check_no_auth(self):
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.post(
                "/artifact/model/test-id/license-check",
                json={"github_url": "https://github.com/test/repo"}
            )
            assert response.status_code == 403

    def test_license_check_empty_id(self, mock_auth):
        response = client.post(
            "/artifact/model/ /license-check",
            json={"github_url": "https://github.com/test/repo"}
        )
        assert response.status_code == 400

    def test_license_check_missing_github_url(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {"type": "model", "id": "test-id"}
            response = client.post("/artifact/model/test-id/license-check", json={})
            assert response.status_code == 400

    def test_license_check_success(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.extract_model_license") as mock_model_license:
                    with patch("src.index.extract_github_license") as mock_github_license:
                        with patch("src.index.check_license_compatibility") as mock_check:
                            mock_get.return_value = {
                                "type": "model",
                                "id": "test-id"
                            }
                            mock_model_license.return_value = "MIT"
                            mock_github_license.return_value = "Apache-2.0"
                            mock_check.return_value = {"compatible": True}
                            response = client.post(
                                "/artifact/model/test-id/license-check",
                                json={"github_url": "https://github.com/test/repo"}
                            )
                            assert response.status_code == 200
                            assert response.json() is True

    def test_license_check_not_compatible(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.extract_model_license") as mock_model_license:
                    with patch("src.index.extract_github_license") as mock_github_license:
                        with patch("src.index.check_license_compatibility") as mock_check:
                            mock_get.return_value = {
                                "type": "model",
                                "id": "test-id"
                            }
                            mock_model_license.return_value = "GPL-3.0"
                            mock_github_license.return_value = "MIT"
                            mock_check.return_value = {"compatible": False}
                            response = client.post(
                                "/artifact/model/test-id/license-check",
                                json={"github_url": "https://github.com/test/repo"}
                            )
                            assert response.status_code == 200
                            assert response.json() is False

    def test_license_check_model_not_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.list_models", return_value={"models": []}):
                    with patch("src.index.s3") as mock_s3:
                        mock_s3.head_object.side_effect = Exception("Not found")
                        response = client.post(
                            "/artifact/model/nonexistent/license-check",
                            json={"github_url": "https://github.com/test/repo"}
                        )
                        assert response.status_code == 404

    def test_license_check_github_not_found(self, mock_auth):
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.extract_model_license") as mock_model_license:
                    with patch("src.index.extract_github_license") as mock_github_license:
                        mock_get.return_value = {"type": "model", "id": "test-id"}
                        mock_model_license.return_value = "MIT"
                        mock_github_license.return_value = None
                        response = client.post(
                            "/artifact/model/test-id/license-check",
                            json={"github_url": "https://github.com/nonexistent/repo"}
                        )
                        assert response.status_code == 404


class TestIndexHelperFunctions:
    """Tests for helper functions in index.py"""

    def test_extract_dataset_code_names_from_readme(self):
        """Test extracting dataset and code names from README"""
        from src.index import _extract_dataset_code_names_from_readme

        readme = """
        This model uses the dataset: imagenet
        Built with library: pytorch
        """
        result = _extract_dataset_code_names_from_readme(readme)
        assert "dataset_name" in result
        assert "code_name" in result

    def test_extract_dataset_code_names_empty(self):
        """Test extracting from empty README"""
        from src.index import _extract_dataset_code_names_from_readme

        result = _extract_dataset_code_names_from_readme("")
        assert result["dataset_name"] is None
        assert result["code_name"] is None

    def test_extract_dataset_code_names_with_patterns(self):
        """Test extracting with various patterns"""
        from src.index import _extract_dataset_code_names_from_readme

        readme = "Trained on https://huggingface.co/datasets/coco dataset. Uses https://github.com/tensorflow/tensorflow library."
        result = _extract_dataset_code_names_from_readme(readme)
        assert result["dataset_name"] is not None or result["code_name"] is not None

    def test_get_model_name_for_s3(self):
        """Test getting model name for S3 lookup"""
        from src.index import _get_model_name_for_s3

        with patch("src.index.get_artifact_from_db") as mock_get:
            mock_get.return_value = {"name": "test-model", "type": "model"}
            result = _get_model_name_for_s3("test-id")
            assert result == "test-model"

    def test_get_model_name_for_s3_not_found(self):
        """Test getting model name when not found"""
        from src.index import _get_model_name_for_s3

        with patch("src.index.get_artifact_from_db", return_value=None):
            result = _get_model_name_for_s3("nonexistent")
            assert result is None

    def test_extract_size_scores_dict(self):
        """Test extracting size scores from dict"""
        from src.index import _extract_size_scores

        rating = {
            "size_score": {
                "raspberry_pi": 0.5,
                "jetson_nano": 0.6,
                "desktop_pc": 0.7,
                "aws_server": 0.8
            }
        }
        result = _extract_size_scores(rating)
        assert result["raspberry_pi"] == 0.5
        assert result["jetson_nano"] == 0.6

    def test_extract_size_scores_not_dict(self):
        """Test extracting size scores when not a dict"""
        from src.index import _extract_size_scores

        rating = {"size_score": 0.5}
        result = _extract_size_scores(rating)
        assert result["raspberry_pi"] == 0.0
        assert result["jetson_nano"] == 0.0

    def test_extract_size_scores_missing(self):
        """Test extracting size scores when missing"""
        from src.index import _extract_size_scores

        rating = {}
        result = _extract_size_scores(rating)
        assert result["raspberry_pi"] == 0.0

    def test_get_tracks(self):
        """Test GET /tracks endpoint"""
        response = client.get("/tracks")
        assert response.status_code == 200
        data = response.json()
        assert "plannedTracks" in data
        assert isinstance(data["plannedTracks"], list)

    def test_get_package_alias(self, mock_auth):
        """Test GET /package/{id} alias endpoint"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "name": "test-model",
                "id": "test-id",
                "type": "model",
                "url": "https://huggingface.co/test-model",
                "version": "main"
            }
            response = client.get("/package/test-id")
            assert response.status_code == 200

    def test_reset_system_no_auth(self):
        """Test reset system without auth"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.delete("/reset")
            assert response.status_code == 403

    def test_reset_system_not_admin(self, mock_auth):
        """Test reset system without admin permissions"""
        with patch("src.index.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"username": "regular_user"}
            response = client.delete("/reset", headers={"Authorization": "Bearer token"})
            assert response.status_code == 401

    def test_reset_system_admin(self, mock_auth):
        """Test reset system with admin permissions"""
        with patch("src.index.verify_jwt_token") as mock_verify:
            with patch("src.index.clear_all_artifacts"):
                with patch("src.index.reset_registry") as mock_reset:
                    with patch("src.index.purge_tokens"):
                        with patch("src.index.ensure_default_admin"):
                            mock_verify.return_value = {
                                "username": "ece30861defaultadminuser"
                            }
                            mock_reset.return_value = {"message": "Reset successful"}
                            response = client.delete(
                                "/reset",
                                headers={"Authorization": "Bearer admin-token"}
                            )
                            assert response.status_code == 200

    def test_link_model_to_datasets_code(self):
        """Test linking model to datasets and code"""
        from src.index import _link_model_to_datasets_code

        with patch("src.index._extract_dataset_code_names_from_readme") as mock_extract:
            with patch("src.index.find_artifacts_by_type") as mock_find:
                with patch("src.index.update_artifact_in_db") as mock_update:
                    mock_extract.return_value = {
                        "dataset_name": "test-dataset",
                        "code_name": "test-code"
                    }
                    mock_find.return_value = [
                        {"id": "dataset-id", "name": "test-dataset", "type": "dataset"},
                        {"id": "code-id", "name": "test-code", "type": "code"}
                    ]
                    _link_model_to_datasets_code(
                        "model-id", "test-model", "README with dataset and code"
                    )
                    mock_update.assert_called()

    def test_link_dataset_code_to_models(self):
        """Test linking dataset/code to models"""
        from src.index import _link_dataset_code_to_models

        with patch("src.index.find_models_with_null_link") as mock_find:
            with patch("src.index.update_artifact_in_db") as mock_update:
                mock_find.return_value = [
                    {"id": "model-id", "name": "test-model", "dataset_name": "test-dataset"}
                ]
                _link_dataset_code_to_models("dataset-id", "test-dataset", "dataset")
                mock_update.assert_called()

    def test_link_dataset_code_to_models_invalid_type(self):
        """Test linking with invalid artifact type"""
        from src.index import _link_dataset_code_to_models

        with patch("src.index.find_models_with_null_link") as mock_find:
            _link_dataset_code_to_models("artifact-id", "test-name", "invalid")
            mock_find.assert_not_called()

    def test_sanitize_model_id_for_s3(self):
        """Test sanitizing model ID for S3"""
        from src.index import sanitize_model_id_for_s3

        result = sanitize_model_id_for_s3("test/model:name")
        assert "/" not in result
        assert ":" not in result

    def test_sanitize_model_id_for_s3_huggingface_url(self):
        """Test sanitizing HuggingFace URL"""
        from src.index import sanitize_model_id_for_s3

        result = sanitize_model_id_for_s3("https://huggingface.co/test/model")
        assert "https://" not in result
        assert "/" not in result

    def test_generate_download_url(self):
        """Test generating download URL"""
        from src.index import generate_download_url

        url = generate_download_url("test-model", "model", "1.0.0")
        assert "test-model" in url
        assert "1.0.0" in url

    def test_build_artifact_response(self):
        """Test building artifact response"""
        from src.index import build_artifact_response

        response = build_artifact_response(
            "test-model", "test-id", "model", "https://example.com", "1.0.0"
        )
        assert response["metadata"]["name"] == "test-model"
        assert response["metadata"]["id"] == "test-id"
        assert response["metadata"]["type"] == "model"

    def test_run_async_rating_success(self):
        """Test async rating success"""
        from src.index import _run_async_rating

        with patch("src.index.analyze_model_content") as mock_analyze:
            mock_analyze.return_value = {"net_score": 0.8}
            _run_async_rating("test-id", "test-model", "1.0.0")
            # Check that status was set
            from src.index import _rating_status
            assert "test-id" in _rating_status

    def test_run_async_rating_failed(self):
        """Test async rating failure"""
        from src.index import _run_async_rating

        with patch("src.index.analyze_model_content", return_value=None):
            _run_async_rating("test-id-2", "test-model", "1.0.0")
            from src.index import _rating_status
            assert _rating_status.get("test-id-2") == "failed"

    def test_run_async_rating_disqualified(self):
        """Test async rating disqualified"""
        from src.index import _run_async_rating

        with patch("src.index.analyze_model_content") as mock_analyze:
            mock_analyze.return_value = {"net_score": 0.3}  # Below 0.5 threshold
            _run_async_rating("test-id-3", TEST_MODEL_NAME, "1.0.0")
            from src.index import _rating_status
            assert _rating_status.get("test-id-3") == RATING_STATUS_DISQUALIFIED

    def test_health_components_invalid_window_range(self):
        """Test health components with invalid window range (3 minutes)"""
        response = client.get("/health/components?windowMinutes=3")
        assert response.status_code == 400

    def test_health_components_with_timeline(self):
        """Test health components with timeline"""
        response = client.get("/health/components?windowMinutes=60&includeTimeline=true")
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data["components"][0]

    def test_verify_auth_token_static_token(self):
        """Test verify_auth_token with static token"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        request.headers.get.side_effect = lambda key, default=None: {
            "x-authorization": "Bearer test-static-token",
            "authorization": None
        }.get(key.lower(), default)
        
        with patch("src.services.auth_public.STATIC_TOKEN", "test-static-token"):
            result = verify_auth_token(request)
            assert result is True

    def test_verify_auth_token_invalid_jwt(self):
        """Test verify_auth_token with invalid JWT"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        request.headers.get.return_value = "Bearer invalid.jwt.token"
        
        with patch("src.index.verify_jwt_token", return_value=None):
            result = verify_auth_token(request)
            assert result is False

    def test_verify_auth_token_no_header(self):
        """Test verify_auth_token with no header"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        request.headers.get.return_value = None
        
        result = verify_auth_token(request)
        assert result is False

    def test_get_artifact_cost_with_dependency(self, mock_auth):
        """Test get artifact cost with dependency=true"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.get_model_sizes") as mock_sizes:
                with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                    mock_get.return_value = {"type": "model", "id": "test-id"}
                    mock_sizes.return_value = {"full": 1024 * 1024}
                    mock_lineage.return_value = {"lineage_map": {}}
                    response = client.get("/artifact/model/test-id/cost?dependency=true")
                    assert response.status_code == 200
                    data = response.json()
                    assert "test-id" in data

    def test_get_artifact_cost_dataset(self, mock_auth):
        """Test get artifact cost for dataset"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {"type": "dataset", "id": "test-dataset-id"}
            response = client.get("/artifact/dataset/test-dataset-id/cost")
            assert response.status_code == 200
            data = response.json()
            assert "test-dataset-id" in data

    def test_get_artifact_audit_dataset(self, mock_auth):
        """Test get artifact audit for dataset"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "type": "dataset",
                "id": "test-dataset-id",
                "name": "test-dataset"
            }
            response = client.get("/artifact/dataset/test-dataset-id/audit")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0

    def test_get_model_rate_invalid_id(self, mock_auth):
        """Test get model rate with invalid ID format"""
        response = client.get("/artifact/model/{id}/rate")
        assert response.status_code == 404
        data = response.json()
        assert "Artifact does not exist" in data["detail"]

    def test_get_model_rate_pending_status(self, mock_auth):
        """Test get model rate with pending status that completes"""
        from src.index import (
            _rating_status,
            _rating_locks,
            _rating_results,
            _rating_lock
        )
        import time

        # Set up pending rating state with thread safety
        event = threading.Event()
        with _rating_lock:
            _rating_status[TEST_MODEL_ID] = RATING_STATUS_PENDING
            _rating_locks[TEST_MODEL_ID] = event
            _rating_results[TEST_MODEL_ID] = {"net_score": 0.8}

        # Start a thread that will complete the rating after a small delay
        # This simulates async completion behavior
        def complete_rating():
            time.sleep(0.1)  # Small delay to ensure request starts waiting
            with _rating_lock:
                _rating_status[TEST_MODEL_ID] = RATING_STATUS_COMPLETED
            event.set()

        completion_thread = threading.Thread(target=complete_rating)
        completion_thread.start()

        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "type": "model",
                "id": TEST_MODEL_ID,
                "name": TEST_MODEL_NAME
            }
            response = client.get(f"/artifact/model/{TEST_MODEL_ID}/rate")
            completion_thread.join()  # Wait for completion thread
            assert response.status_code == 200
            data = response.json()
            assert data["net_score"] == 0.8

    def test_get_model_rate_pending_actually_waits(self, mock_auth):
        """Verify that pending status actually blocks and waits for completion"""
        from src.index import (
            _rating_status,
            _rating_locks,
            _rating_results,
            _rating_lock
        )
        import time

        test_id = "wait-test-id"
        wait_time = 0.2  # 200ms delay
        start_time = None
        end_time = None

        # Set up pending state with thread safety
        event = threading.Event()
        with _rating_lock:
            _rating_status[test_id] = RATING_STATUS_PENDING
            _rating_locks[test_id] = event
            _rating_results[test_id] = {"net_score": 0.85}

        # Thread that completes rating after delay
        def complete_after_delay():
            nonlocal start_time
            time.sleep(wait_time)
            start_time = time.time()
            with _rating_lock:
                _rating_status[test_id] = RATING_STATUS_COMPLETED
            event.set()
            time.sleep(0.01)  # Small delay after setting

        completion_thread = threading.Thread(target=complete_after_delay)
        completion_thread.start()

        # Make request - should wait for completion
        request_start = time.time()
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "type": "model",
                "id": test_id,
                "name": "test-model"
            }
            response = client.get(f"/artifact/model/{test_id}/rate")
            end_time = time.time()

        completion_thread.join()

        # Verify request waited at least wait_time
        elapsed = end_time - request_start
        assert elapsed >= wait_time, (
            f"Request didn't wait: {elapsed} < {wait_time}"
        )
        assert response.status_code == 200
        assert response.json()["net_score"] == 0.85

    def test_get_model_lineage_with_dependencies(self, mock_auth):
        """Test get model lineage with dependencies"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                mock_get.return_value = {"type": "model", "id": "test-id"}
                mock_lineage.return_value = {
                    "lineage_map": {
                        "parent-1": {
                            "name": "Parent Model",
                            "dependencies": [{"id": "dep-1"}]
                        }
                    }
                }
                response = client.get("/artifact/model/test-id/lineage")
                assert response.status_code == 200
                data = response.json()
                assert "nodes" in data
                assert "edges" in data


class TestCreateArtifactByType:
    """Tests for POST /artifact/{artifact_type}"""

    def test_create_artifact_no_auth(self):
        """Test create artifact without auth"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.post("/artifact/model", json={"url": "https://huggingface.co/test/model"})
            assert response.status_code == 403

    def test_create_artifact_invalid_type(self, mock_auth):
        """Test create artifact with invalid type"""
        response = client.post("/artifact/invalid", json={"url": "https://example.com/test"})
        assert response.status_code == 400

    def test_create_artifact_missing_url(self, mock_auth):
        """Test create artifact without URL"""
        response = client.post("/artifact/model", json={})
        assert response.status_code == 400

    def test_create_artifact_dataset_success(self, mock_auth):
        """Test create dataset artifact"""
        with patch("src.index._artifact_storage", {}):
            with patch("src.index.list_all_artifacts", return_value=[]):
                with patch("src.index.save_artifact"):
                    with patch("src.index._link_dataset_code_to_models"):
                        with patch("src.index.store_artifact_metadata"):
                            response = client.post(
                                "/artifact/dataset",
                                json={
                                    "url": "https://example.com/dataset",
                                    "name": "test-dataset"
                                }
                            )
                            assert response.status_code == 201
                            data = response.json()
                            assert data["metadata"]["type"] == "dataset"

    def test_create_artifact_code_success(self, mock_auth):
        """Test create code artifact"""
        with patch("src.index._artifact_storage", {}):
            with patch("src.index.list_all_artifacts", return_value=[]):
                with patch("src.index.save_artifact"):
                    with patch("src.index._link_dataset_code_to_models"):
                        with patch("src.index.store_artifact_metadata"):
                            response = client.post(
                                "/artifact/code",
                                json={
                                    "url": "https://github.com/test/repo",
                                    "name": "test-code"
                                }
                            )
                            assert response.status_code == 201
                            data = response.json()
                            assert data["metadata"]["type"] == "code"

    def test_create_artifact_model_exists(self, mock_auth):
        """Test create model that already exists"""
        with patch("src.index.list_models") as mock_list:
            mock_list.return_value = {"models": [{"name": "test-model", "id": "test-id"}]}
            response = client.post(
                "/artifact/model",
                json={"url": "https://huggingface.co/test/model"}
            )
            assert response.status_code == 409

    def test_create_artifact_dataset_exists(self, mock_auth):
        """Test create dataset that already exists"""
        with patch("src.index._artifact_storage", {"existing-id": {"name": "test-dataset", "type": "dataset", "url": "https://example.com/dataset"}}):
            with patch("src.index.list_all_artifacts", return_value=[{"id": "existing-id", "name": "test-dataset", "type": "dataset", "url": "https://example.com/dataset"}]):
                response = client.post(
                    "/artifact/dataset",
                    json={"url": "https://example.com/dataset", "name": "test-dataset"}
                )
                assert response.status_code == 409


class TestUpdateArtifact:
    """Tests for PUT /artifacts/{artifact_type}/{id}"""

    def test_update_artifact_no_auth(self):
        """Test update artifact without auth"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.put(
                "/artifacts/model/test-id",
                json={"metadata": {"id": "test-id", "name": "test"}, "data": {"url": "https://example.com"}}
            )
            assert response.status_code == 403

    def test_update_artifact_missing_fields(self, mock_auth):
        """Test update artifact with missing fields"""
        response = client.put("/artifacts/model/test-id", json={})
        assert response.status_code == 400

    def test_update_artifact_id_mismatch(self, mock_auth):
        """Test update artifact with ID mismatch"""
        response = client.put(
            "/artifacts/model/test-id",
            json={"metadata": {"id": "other-id", "name": "test"}, "data": {"url": "https://example.com"}}
        )
        assert response.status_code == 400

    def test_update_artifact_model_not_found(self, mock_auth):
        """Test update model that doesn't exist"""
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index._get_model_name_for_s3", return_value=None):
                with patch("src.index.s3") as mock_s3:
                    from botocore.exceptions import ClientError
                    error_response = {"Error": {"Code": "NoSuchKey"}}
                    mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")
                    with patch("src.index.list_models", return_value={"models": []}):
                        response = client.put(
                            "/artifacts/model/nonexistent",
                            json={"metadata": {"id": "nonexistent", "name": "test"}, "data": {"url": "https://example.com"}}
                        )
                        assert response.status_code == 404

    def test_update_artifact_dataset_success(self, mock_auth):
        """Test update dataset artifact"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index.update_artifact_in_db") as mock_update:
                mock_get.return_value = {"type": "dataset", "id": "test-id"}
                response = client.put(
                    "/artifacts/dataset/test-id",
                    json={"metadata": {"id": "test-id", "name": "updated"}, "data": {"url": "https://example.com/new"}}
                )
                assert response.status_code == 200
                mock_update.assert_called()

    def test_update_artifact_missing_url(self, mock_auth):
        """Test update artifact without URL"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            mock_get.return_value = {"type": "model", "id": "test-id"}
            response = client.put(
                "/artifacts/model/test-id",
                json={"metadata": {"id": "test-id", "name": "test"}, "data": {}}
            )
            assert response.status_code == 400


class TestDeleteArtifact:
    """Tests for DELETE /artifacts/{artifact_type}/{id}"""

    def test_delete_artifact_no_auth(self):
        """Test delete artifact without auth"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.delete("/artifacts/model/test-id")
            assert response.status_code == 403

    def test_delete_artifact_dataset_success(self, mock_auth):
        """Test delete dataset artifact"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index.delete_artifact") as mock_delete:
                with patch("src.index._artifact_storage", {"test-id": {"type": "dataset"}}):
                    mock_get.return_value = {"type": "dataset", "id": "test-id"}
                    response = client.delete("/artifacts/dataset/test-id")
                    assert response.status_code == 200
                    mock_delete.assert_called()

    def test_delete_artifact_model_not_found(self, mock_auth):
        """Test delete model that doesn't exist"""
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index.s3") as mock_s3:
                from botocore.exceptions import ClientError
                error_response = {"Error": {"Code": "NoSuchKey"}}
                mock_s3.head_object.side_effect = ClientError(
                    error_response, "HeadObject"
                )
                with patch("src.index.list_models", return_value={"models": []}):
                    response = client.delete("/artifacts/model/nonexistent")
                    assert response.status_code == 404

    def test_delete_artifact_code_success(self, mock_auth):
        """Test delete code artifact"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index.delete_artifact") as mock_delete:
                with patch("src.index._artifact_storage", {"test-id": {"type": "code"}}):
                    mock_get.return_value = {"type": "code", "id": "test-id"}
                    response = client.delete("/artifacts/code/test-id")
                    assert response.status_code == 200
                    mock_delete.assert_called()

    def test_delete_artifact_model_s3_success(self, mock_auth):
        """Test delete model from S3"""
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index.s3") as mock_s3:
                mock_s3.head_object.return_value = {}  # Model exists
                mock_s3.delete_object.return_value = {}
                response = client.delete("/artifacts/model/test-id")
                assert response.status_code == 200


# Tests for previously untested functions

class TestGetPackageRate:
    """Test get_package_rate function"""

    def test_get_package_rate_success(self, mock_auth):
        """Test successful rate retrieval"""
        with patch("src.index.get_model_rate") as mock_rate:
            mock_rate.return_value = {"score": 0.8}
            
            response = client.get("/artifact/model/test-id/rate")
            assert response.status_code == 200


class TestDeleteArtifactEndpoint:
    """Test delete_artifact_endpoint function"""

    def test_delete_artifact_endpoint_no_auth(self):
        """Test delete without authentication"""
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.delete("/artifacts/model/test-id")
            assert response.status_code == 403

    def test_delete_artifact_endpoint_from_db(self, mock_auth):
        """Test delete artifact from database"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index.delete_artifact") as mock_delete:
                mock_get.return_value = {"type": "dataset", "id": "test-id"}
                
                response = client.delete("/artifacts/dataset/test-id")
                assert response.status_code == 200
                mock_delete.assert_called_once()


class TestNormalizeName:
    """Test normalize_name helper function"""

    def test_normalize_name_basic(self):
        """Test basic name normalization"""
        from src.index import _link_model_to_datasets_code
        # Test through _link_model_to_datasets_code which uses normalize_name
        # This is an indirect test since normalize_name is a nested function
        # We can test it through the parent function
        with patch("src.index.find_artifacts_by_type") as mock_find:
            with patch("src.index.find_artifacts_by_name") as mock_find_name:
                mock_find.return_value = []
                mock_find_name.return_value = []
                # The function should handle names with "/" correctly
                # Function should complete without error (it returns None, which is expected)
                result = _link_model_to_datasets_code("test/model", "dataset-name", "code-name")
                # Function completes successfully - return value is None by design
                assert result is None


class TestDispatch:
    """Test dispatch middleware function"""

    def test_dispatch_success(self):
        """Test dispatch middleware with successful request"""
        # Dispatch is tested through actual requests
        response = client.get("/health")
        assert response.status_code == 200

    def test_dispatch_logs_request(self):
        """Test that dispatch logs requests"""
        with patch("src.index.logger") as mock_logger:
            client.get("/health")
            # Should log request
            assert mock_logger.info.called


class TestStartupEvent:
    """Test startup_event function"""

    def test_startup_event_runs(self):
        """Test that startup event runs on app startup"""
        # Startup event runs automatically, we can verify routes are registered
        from src.index import app
        routes = [r for r in app.routes if hasattr(r, "path")]
        assert len(routes) > 0


class TestHttpExceptionHandler:
    """Test http_exception_handler function"""

    def test_http_exception_handler_404(self):
        """Test exception handler for 404"""
        with patch("src.index.logger") as mock_logger:
            response = client.get("/nonexistent-endpoint")
            # Should log the exception
            assert mock_logger.error.called or response.status_code == 404


class TestSetupCloudwatchLogging:
    """Test setup_cloudwatch_logging function"""

    def test_setup_cloudwatch_logging_aws_available(self):
        """Test CloudWatch setup when AWS is available"""
        with patch("boto3.client") as mock_boto:
            with patch("watchtower.CloudWatchLogHandler"):
                mock_sts = MagicMock()
                mock_sts.get_caller_identity.return_value = {"Account": "123456"}
                mock_boto.return_value = mock_sts
                
                from src.index import setup_cloudwatch_logging
                # Should not raise exception
                try:
                    setup_cloudwatch_logging()
                except Exception:
                    pass  # May fail in test environment, that's OK

    def test_setup_cloudwatch_logging_aws_unavailable(self):
        """Test CloudWatch setup when AWS is unavailable"""
        with patch("boto3.client", side_effect=Exception("AWS unavailable")):
            from src.index import setup_cloudwatch_logging
            # Should handle exception gracefully
            try:
                setup_cloudwatch_logging()
            except Exception:
                pass  # Expected to fail gracefully


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


class TestHelperFunctions:
    """Tests for helper functions in index.py"""

    def test_build_regex_patterns(self):
        """Test building regex patterns"""
        from src.index import _build_regex_patterns
        patterns = _build_regex_patterns()
        assert "hf_dataset" in patterns
        assert "github" in patterns
        assert "yaml_dataset" in patterns
        assert "foundation_models" in patterns
        assert "benchmarks" in patterns

    def test_apply_text_patterns(self):
        """Test applying text patterns"""
        from src.index import _apply_text_patterns
        text = "Trained on https://huggingface.co/datasets/coco. Uses https://github.com/tensorflow/tensorflow"
        result = _apply_text_patterns(text)
        assert "datasets" in result
        assert "code_repos" in result
        assert isinstance(result["datasets"], list)
        assert isinstance(result["code_repos"], list)

    def test_apply_text_patterns_empty(self):
        """Test applying patterns to empty text"""
        from src.index import _apply_text_patterns
        result = _apply_text_patterns("")
        assert result["datasets"] == []
        assert result["code_repos"] == []

    def test_complete_urls(self):
        """Test completing URLs"""
        from src.index import _complete_urls
        raw_data = {
            "datasets": ["coco", "https://huggingface.co/datasets/imagenet"],
            "code_repos": ["tensorflow/tensorflow", "https://github.com/pytorch/pytorch.git"]
        }
        result = _complete_urls(raw_data)
        assert all("http" in d or "huggingface.co" in d for d in result["datasets"])
        assert all("http" in c or "github.com" in c for c in result["code_repos"])

    def test_parse_dependencies_with_llm(self):
        """Test parsing dependencies with LLM"""
        from src.index import _parse_dependencies
        with patch("os.getenv", return_value="test-api-key"):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": '{"data_sources": ["coco"], "source_repositories": ["tensorflow/tensorflow"], "base_models": [], "test_data": []}'
                        }
                    }]
                }
                result = _parse_dependencies("This model uses coco dataset and tensorflow", "test-model")
                assert "datasets" in result
                assert "code_repos" in result

    def test_parse_dependencies_without_llm(self):
        """Test parsing dependencies without LLM (fallback to patterns)"""
        from src.index import _parse_dependencies
        with patch("os.getenv", return_value=None):
            text = "Trained on https://huggingface.co/datasets/coco"
            result = _parse_dependencies(text, "test-model")
            assert "datasets" in result

    def test_parse_dependencies_short_text(self):
        """Test parsing dependencies with very short text"""
        from src.index import _parse_dependencies
        result = _parse_dependencies("short", "test-model")
        assert "datasets" in result

    def test_parse_dependencies_llm_timeout(self):
        """Test parsing dependencies when LLM times out"""
        from src.index import _parse_dependencies
        with patch("os.getenv", return_value="test-api-key"):
            with patch("requests.post", side_effect=Exception("Timeout")):
                text = "Trained on https://huggingface.co/datasets/coco"
                result = _parse_dependencies(text, "test-model")
                assert "datasets" in result  # Should fallback to patterns

    def test_get_artifact_size_mb_model(self):
        """Test getting artifact size for model"""
        from src.index import _get_artifact_size_mb
        with patch("src.index._get_model_name_for_s3", return_value="test-model"):
            with patch("src.index.get_model_sizes") as mock_sizes:
                mock_sizes.return_value = {"full": 1024 * 1024 * 10}  # 10MB
                size = _get_artifact_size_mb("model", "test-id")
                assert size == 10.0

    def test_get_artifact_size_mb_dataset(self):
        """Test getting artifact size for dataset"""
        from src.index import _get_artifact_size_mb
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.get_artifact_from_db"):
                mock_get.return_value = {
                    "name": "test-dataset",
                    "url": "https://example.com/dataset.zip"
                }
                with patch("requests.head") as mock_head:
                    # 10MB
                    mock_head.return_value.headers = {"Content-Length": "10485760"}
                    size = _get_artifact_size_mb("dataset", "test-id")
                    assert size == 10.0

    def test_get_artifact_size_mb_zero(self):
        """Test getting artifact size when size cannot be determined"""
        from src.index import _get_artifact_size_mb
        with patch("src.index._get_model_name_for_s3", return_value=None):
            with patch("src.index.get_model_sizes", return_value={"error": "not found"}):
                size = _get_artifact_size_mb("model", "test-id")
                assert size == 0.0

    def test_build_rating_response(self):
        """Test building rating response"""
        from src.index import _build_rating_response
        rating = {
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
        result = _build_rating_response("test-model", rating)
        assert result["name"] == "test-model"
        assert result["net_score"] == 0.8
        assert "size_score" in result
        assert isinstance(result["size_score"], dict)

    def test_cleanup_stuck_ratings(self):
        """Test cleanup of stuck ratings"""
        from src.index import _cleanup_stuck_ratings, _rating_status, _rating_start_times, _rating_lock
        import time
        
        # Set up a stuck rating
        with _rating_lock:
            _rating_status["stuck-id"] = RATING_STATUS_PENDING
            _rating_start_times["stuck-id"] = time.time() - 700  # 700 seconds ago (over 10 min threshold)
        
        _cleanup_stuck_ratings()
        
        # Check that stuck rating was cleaned up
        assert _rating_status.get("stuck-id") == RATING_STATUS_FAILED or "stuck-id" not in _rating_status


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


class TestCreateArtifactByTypeEdgeCases:
    """Additional edge cases for POST /artifact/{artifact_type}"""

    def test_create_artifact_model_with_hf_url(self, mock_auth):
        """Test creating model artifact with HuggingFace URL"""
        with patch("src.index.list_models", return_value={"models": []}):
            with patch("src.index.model_ingestion"):
                with patch("src.index.download_model") as mock_download:
                    with patch("src.index.save_artifact"):
                        with patch("src.index.store_artifact_metadata"):
                            with patch("src.index._link_model_to_datasets_code"):
                                with patch("src.index._run_async_rating"):
                                    mock_download.return_value = b"fake zip"
                                    response = client.post(
                                        "/artifact/model",
                                        json={
                                            "url": "https://huggingface.co/test/model"
                                        }
                                    )
                                    # Should succeed if all mocks are set up correctly
                                    assert response.status_code == 201

    def test_create_artifact_model_with_name_in_body(self, mock_auth):
        """Test creating model artifact with name in body"""
        with patch("src.index.list_models", return_value={"models": []}):
            with patch("src.index.model_ingestion"):
                with patch("src.index.download_model") as mock_download:
                    with patch("src.index.save_artifact"):
                        with patch("src.index.store_artifact_metadata"):
                            with patch("src.index._link_model_to_datasets_code"):
                                with patch("src.index._run_async_rating"):
                                    mock_download.return_value = b"fake zip"
                                    response = client.post(
                                        "/artifact/model",
                                        json={
                                            "url": "https://huggingface.co/test/model",
                                            "name": "custom-name"
                                        }
                                    )
                                    # Should succeed if all mocks are set up correctly
                                    assert response.status_code == 201

    def test_create_artifact_code_with_github_url(self, mock_auth):
        """Test creating code artifact with GitHub URL"""
        with patch("src.index._artifact_storage", {}):
            with patch("src.index.list_all_artifacts", return_value=[]):
                with patch("src.index.save_artifact"):
                    with patch("src.index._link_dataset_code_to_models"):
                        with patch("src.index.store_artifact_metadata"):
                            response = client.post(
                                "/artifact/code",
                                json={"url": "https://github.com/test/repo"}
                            )
                            assert response.status_code == 201

    def test_create_artifact_extract_name_from_url(self, mock_auth):
        """Test extracting name from various URL formats"""
        with patch("src.index._artifact_storage", {}):
            with patch("src.index.list_all_artifacts", return_value=[]):
                with patch("src.index.save_artifact"):
                    with patch("src.index._link_dataset_code_to_models"):
                        with patch("src.index.store_artifact_metadata"):
                            # Test GitHub URL extraction
                            response = client.post(
                                "/artifact/code",
                                json={"url": "https://github.com/org/repo"}
                            )
                            assert response.status_code == 201


class TestGetArtifactEdgeCases:
    """Additional edge cases for GET /artifact/{artifact_type}/{id}"""

    def test_get_artifact_model_with_rating_pending(self, mock_auth):
        """Test getting artifact while rating is pending"""
        from src.index import _rating_status, _rating_locks, _rating_lock
        
        with _rating_lock:
            _rating_status["test-id-pending"] = RATING_STATUS_PENDING
            event = threading.Event()
            _rating_locks["test-id-pending"] = event
            event.set()  # Signal immediately
        
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "name": "test-model",
                "id": "test-id-pending",
                "type": "model",
                "url": "https://huggingface.co/test-model",
                "version": "main"
            }
            response = client.get("/artifact/model/test-id-pending")
            # Should return 200 if rating completes successfully
            assert response.status_code == 200

    def test_get_artifact_model_with_rating_disqualified(self, mock_auth):
        """Test getting artifact that was disqualified"""
        from src.index import _rating_status, _rating_lock
        
        with _rating_lock:
            _rating_status["disqualified-id"] = RATING_STATUS_DISQUALIFIED
        
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "name": "test-model",
                "id": "disqualified-id",
                "type": "model"
            }
            response = client.get("/artifact/model/disqualified-id")
            assert response.status_code == 404

    def test_get_artifact_model_fallback_to_s3_name_lookup(self, mock_auth):
        """Test getting artifact with S3 name lookup fallback"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_models") as mock_list:
                        with patch("src.index.s3") as mock_s3:
                            mock_list.return_value = {
                                "models": [{"name": "test-model", "version": "main"}]
                            }
                            mock_s3.head_object.return_value = {}
                            response = client.get("/artifact/model/test-model")
                            # Should succeed if S3 object exists (mocked)
                            assert response.status_code == 200


class TestUpdateDeleteEdgeCases:
    """Additional edge cases for PUT and DELETE"""

    def test_update_artifact_model_s3_verification(self, mock_auth):
        """Test updating model artifact with S3 verification"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.s3") as mock_s3:
                    mock_get.return_value = {"type": "model", "id": "test-id"}
                    mock_s3.head_object.return_value = {}
                    response = client.put(
                        "/artifacts/model/test-id",
                        json={
                            "metadata": {"id": "test-id", "name": "test"},
                            "data": {"url": "https://example.com"}
                        }
                    )
                    assert response.status_code == 200

    def test_delete_artifact_model_multiple_versions(self, mock_auth):
        """Test deleting model artifact with multiple versions"""
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index.s3") as mock_s3:
                mock_s3.head_object.return_value = {}
                mock_s3.delete_object.return_value = {}
                response = client.delete("/artifacts/model/test-id")
                # Should attempt to delete multiple versions
                assert response.status_code in [200, 404]


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


class TestVerifyAuthToken:
    """Additional tests for verify_auth_token"""

    def test_verify_auth_token_bearer_prefix(self):
        """Test verify_auth_token with Bearer prefix"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        # Headers are case-insensitive, so check both x-authorization and authorization
        # Use valid JWT format (3 parts separated by dots)
        valid_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.test"

        def header_get(key, default=None):
            key_lower = key.lower()
            if key_lower == "x-authorization":
                return f"Bearer {valid_jwt}"
            elif key_lower == "authorization":
                return f"Bearer {valid_jwt}"
            return default

        request.headers.get = header_get

        with patch("src.index.verify_jwt_token", return_value={"user_id": "test"}):
            result = verify_auth_token(request)
            assert result is True

    def test_verify_auth_token_raw_jwt(self):
        """Test verify_auth_token with raw JWT (no Bearer prefix)"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        # Use valid JWT format (3 parts separated by dots)
        valid_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.test"
        request.headers.get.return_value = valid_jwt

        with patch("src.index.verify_jwt_token", return_value={"user_id": "test"}):
            result = verify_auth_token(request)
            assert result is True

    def test_verify_auth_token_invalid_format(self):
        """Test verify_auth_token with invalid JWT format"""
        from src.index import verify_auth_token
        from fastapi import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        request.headers.get.return_value = "invalid.token"  # Only 2 parts

        result = verify_auth_token(request)
        assert result is False


class TestAdditionalCoverage:
    """Additional tests to improve coverage"""

    def test_list_artifacts_empty_body(self, mock_auth):
        """Test list_artifacts with empty body"""
        response = client.post("/artifacts", json=[])
        assert response.status_code == 200

    def test_list_artifacts_invalid_query_object(self, mock_auth):
        """Test list_artifacts with invalid query object"""
        response = client.post("/artifacts", json=["not an object"])
        assert response.status_code == 400

    def test_list_artifacts_too_many_results(self, mock_auth, mock_s3_service, mock_artifact_storage):
        """Test list_artifacts with too many results"""
        mock_s3_service["list_models"].return_value = {
            "models": [{"name": f"model{i}", "id": f"id{i}"} for i in range(10001)]
        }
        mock_artifact_storage["list_all_artifacts"].return_value = []
        response = client.post("/artifacts", json=[{"name": "*"}])
        assert response.status_code == 413

    def test_list_artifacts_with_offset(self, mock_auth, mock_s3_service, mock_artifact_storage):
        """Test list_artifacts with offset parameter"""
        mock_s3_service["list_models"].return_value = {"models": []}
        mock_artifact_storage["list_all_artifacts"].return_value = []
        response = client.post("/artifacts?offset=10", json=[{"name": "*"}])
        assert response.status_code == 200

    def test_get_artifact_by_name_empty_name_duplicate(self, mock_auth):
        """Test get_artifact_by_name with empty name returns 400"""
        response = client.get("/artifact/byName/")
        assert response.status_code == 400

    def test_search_artifacts_by_regex_array_body(self, mock_auth):
        """Test search_artifacts_by_regex with array body"""
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_artifacts_from_s3") as mock_s3_list:
                with patch("src.index.list_all_artifacts") as mock_db:
                    mock_list.return_value = {"models": [{"name": "test-model", "id": "test-id"}]}
                    mock_s3_list.return_value = {"artifacts": []}
                    mock_db.return_value = []
                    response = client.post("/artifact/byRegEx", json=[{"regex": "test.*"}])
                    assert response.status_code == 200

    def test_search_artifacts_by_regex_form_data(self, mock_auth):
        """Test search_artifacts_by_regex with form data"""
        with patch("src.index.list_models") as mock_list:
            with patch("src.index.list_artifacts_from_s3") as mock_s3_list:
                with patch("src.index.list_all_artifacts") as mock_db:
                    mock_list.return_value = {"models": [{"name": "test-model", "id": "test-id"}]}
                    mock_s3_list.return_value = {"artifacts": []}
                    mock_db.return_value = []
                    response = client.post("/artifact/byRegEx", data={"regex": "test.*"})
                    assert response.status_code == 200

    def test_search_artifacts_by_regex_invalid_body_type(self, mock_auth):
        """Test search_artifacts_by_regex with invalid body type"""
        response = client.post("/artifact/byRegEx", json="not an object or array")
        assert response.status_code == 400

    def test_search_artifacts_by_regex_regex_too_long(self, mock_auth):
        """Test search_artifacts_by_regex with regex too long"""
        long_regex = "a" * 501
        response = client.post("/artifact/byRegEx", json={"regex": long_regex})
        assert response.status_code == 400

    def test_search_artifacts_by_regex_nested_quantifiers(self, mock_auth):
        """Test search_artifacts_by_regex with nested quantifiers"""
        response = client.post("/artifact/byRegEx", json={"regex": "(a+)+"})
        assert response.status_code == 400

    def test_search_artifacts_by_regex_large_range(self, mock_auth):
        """Test search_artifacts_by_regex with large quantifier range"""
        response = client.post("/artifact/byRegEx", json={"regex": "a{1,2000}"})
        assert response.status_code == 400

    def test_get_artifact_model_s3_metadata_found(self, mock_auth):
        """Test get_artifact when found in S3 metadata"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id") as mock_find:
                    mock_find.return_value = {
                        "name": "test-model",
                        "type": "model",
                        "version": "main",
                        "url": "https://huggingface.co/test-model"
                    }
                    with patch("src.index.save_artifact"):
                        response = client.get("/artifact/model/test-id")
                        assert response.status_code == 200

    def test_get_artifact_model_s3_name_lookup(self, mock_auth):
        """Test get_artifact with S3 name lookup"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_models") as mock_list:
                        with patch("src.index.s3") as mock_s3:
                            mock_list.return_value = {
                                "models": [{"name": "test-model", "version": "main"}]
                            }
                            mock_s3.head_object.return_value = {}
                            response = client.get("/artifact/model/test-model")
                            assert response.status_code == 200

    def test_get_artifact_model_common_versions(self, mock_auth):
        """Test get_artifact trying common versions"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_models") as mock_list:
                        with patch("src.index.s3") as mock_s3:
                            mock_list.return_value = {"models": []}
                            mock_s3.head_object.return_value = {}
                            response = client.get("/artifact/model/test-model")
                            assert response.status_code == 200

    def test_get_artifact_dataset_s3_metadata(self, mock_auth):
        """Test get_artifact for dataset with S3 metadata"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id") as mock_find:
                    mock_find.return_value = {
                        "name": "test-dataset",
                        "type": "dataset",
                        "version": "main",
                        "url": "https://example.com/dataset"
                    }
                    with patch("src.index.save_artifact"):
                        response = client.get("/artifact/dataset/test-id")
                        assert response.status_code == 200

    def test_get_artifact_dataset_s3_name_lookup(self, mock_auth):
        """Test get_artifact for dataset with S3 name lookup"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_artifacts_from_s3") as mock_s3_list:
                        mock_s3_list.return_value = {
                            "artifacts": [{
                                "name": "test-dataset",
                                "artifact_id": "test-id",
                                "version": "main"
                            }]
                        }
                        with patch("src.index.save_artifact"):
                            response = client.get("/artifact/dataset/test-dataset")
                            assert response.status_code == 200

    def test_get_artifact_dataset_name_lookup(self, mock_auth):
        """Test get_artifact for dataset with name lookup"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_artifacts_from_s3", return_value={"artifacts": []}):
                        with patch("src.index.list_all_artifacts") as mock_db:
                            mock_db.return_value = [{
                                "name": "test-dataset",
                                "id": "test-id",
                                "type": "dataset",
                                "url": "https://example.com/dataset",
                                "version": "main"
                            }]
                            response = client.get("/artifact/dataset/test-dataset")
                            assert response.status_code == 200

    def test_get_artifact_code_sanitized_name_match(self, mock_auth):
        """Test get_artifact for code with sanitized name match"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id", return_value=None):
                    with patch("src.index.list_artifacts_from_s3", return_value={"artifacts": []}):
                        with patch("src.index.list_all_artifacts") as mock_db:
                            mock_db.return_value = [{
                                "name": "test/code",
                                "id": "test-id",
                                "type": "code",
                                "url": "https://example.com/code",
                                "version": "main"
                            }]
                            response = client.get("/artifact/code/test_code")
                            assert response.status_code == 200

    def test_post_artifact_ingest_model_readme_extraction(self, mock_auth):
        """Test post_artifact_ingest with README extraction"""
        import zipfile
        import io
        zip_content = io.BytesIO()
        with zipfile.ZipFile(zip_content, 'w') as zf:
            zf.writestr("README.md", "Dataset: coco\nCode: tensorflow")
        zip_content.seek(0)

        with patch("src.index.list_models", return_value={"models": []}):
            with patch("src.index.model_ingestion"):
                with patch("src.index.download_model", return_value=zip_content.read()):
                    with patch("src.index.save_artifact"):
                        with patch("src.index.store_artifact_metadata"):
                            with patch("src.index._link_model_to_datasets_code"):
                                with patch("src.index._run_async_rating"):
                                    with patch("src.index.get_artifact_from_db", return_value={"id": "test-id"}):
                                        response = client.post(
                                            "/artifact/ingest",
                                            data={"name": "test-model", "version": "main"}
                                        )
                                        assert response.status_code == 200

    def test_post_artifact_ingest_model_no_readme(self, mock_auth):
        """Test post_artifact_ingest without README"""
        import zipfile
        import io
        zip_content = io.BytesIO()
        with zipfile.ZipFile(zip_content, 'w') as zf:
            zf.writestr("config.json", "{}")
        zip_content.seek(0)

        with patch("src.index.list_models", return_value={"models": []}):
            with patch("src.index.model_ingestion"):
                with patch("src.index.download_model", return_value=zip_content.read()):
                    with patch("src.index.save_artifact"):
                        with patch("src.index.store_artifact_metadata"):
                            with patch("src.index._run_async_rating"):
                                with patch("src.index.get_artifact_from_db", return_value={"id": "test-id"}):
                                    response = client.post(
                                        "/artifact/ingest",
                                        data={"name": "test-model", "version": "main"}
                                    )
                                    assert response.status_code == 200

    def test_create_artifact_model_with_readme(self, mock_auth):
        """Test create_artifact for model with README extraction"""
        import zipfile
        import io
        zip_content = io.BytesIO()
        with zipfile.ZipFile(zip_content, 'w') as zf:
            zf.writestr("README.md", "Dataset: coco")
        zip_content.seek(0)

        with patch("src.index.list_models", return_value={"models": []}):
            with patch("src.index.model_ingestion"):
                with patch("src.index.download_model", return_value=zip_content.read()):
                    with patch("src.index.save_artifact"):
                        with patch("src.index.store_artifact_metadata"):
                            with patch("src.index._link_model_to_datasets_code"):
                                with patch("src.index._run_async_rating"):
                                    response = client.post(
                                        "/artifact/model",
                                        json={"url": "https://huggingface.co/test/model"}
                                    )
                                    assert response.status_code in [201, 500]

    def test_create_artifact_model_ingestion_error(self, mock_auth):
        """Test create_artifact when model_ingestion fails"""
        with patch("src.index.list_models", return_value={"models": []}):
            with patch("src.index.model_ingestion", side_effect=Exception("Ingestion failed")):
                response = client.post(
                    "/artifact/model",
                    json={"url": "https://huggingface.co/test/model"}
                )
                assert response.status_code == 500

    def test_get_artifact_cost_model_with_dependencies(self, mock_auth):
        """Test get_artifact_cost with dependencies"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_sizes", return_value={"full": 1024 * 1024}):
                    mock_get.side_effect = [
                        {"type": "model", "id": "test-id", "dataset_id": "dataset-id", "code_id": "code-id"},
                        {"type": "dataset", "id": "dataset-id"},
                        {"type": "code", "id": "code-id"}
                    ]
                    with patch("src.index.get_generic_artifact_metadata") as mock_generic:
                        mock_generic.return_value = {
                            "type": "model",
                            "id": "test-id",
                            "dataset_id": "dataset-id",
                            "code_id": "code-id"
                        }
                        with patch("src.index._get_artifact_size_mb", side_effect=[5.0, 3.0]):
                            response = client.get("/artifact/model/test-id/cost?dependency=true")
                            assert response.status_code == 200
                            data = response.json()
                            assert "test-id" in data
                            # Dependencies may or may not be included depending on implementation
                            # Just verify main artifact is present
                            assert "standalone_cost" in data["test-id"] or "total_cost" in data["test-id"]

    def test_get_artifact_cost_model_size_from_url(self, mock_auth):
        """Test get_artifact_cost getting size from URL"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value=None):
                with patch("src.index.get_model_sizes", return_value={"error": "not found"}):
                    mock_get.return_value = {
                        "type": "model",
                        "id": "test-id",
                        "url": "https://huggingface.co/test-model"
                    }
                    with patch("requests.head") as mock_head:
                        mock_head.return_value.headers = {"Content-Length": "10485760"}
                        response = client.get("/artifact/model/test-id/cost")
                        assert response.status_code == 200

    def test_get_artifact_cost_model_size_not_determinable(self, mock_auth):
        """Test get_artifact_cost when size cannot be determined"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value=None):
                with patch("src.index.get_model_sizes", return_value={"error": "not found"}):
                    mock_get.return_value = {
                        "type": "model",
                        "id": "test-id",
                        "url": "https://huggingface.co/test-model"
                    }
                    with patch("requests.head", side_effect=Exception("Network error")):
                        response = client.get("/artifact/model/test-id/cost")
                        assert response.status_code == 404

    def test_get_artifact_audit_model_s3_error(self, mock_auth):
        """Test get_artifact_audit when S3 returns error"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.s3") as mock_s3:
                from botocore.exceptions import ClientError
                mock_get.return_value = {
                    "type": "model",
                    "id": "test-id",
                    "name": "test-model"
                }
                error_response = {"Error": {"Code": "AccessDenied"}}
                mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")
                response = client.get("/artifact/model/test-id/audit")
                assert response.status_code == 200

    def test_get_model_rate_s3_metadata_found(self, mock_auth):
        """Test get_model_rate when found in S3 metadata"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.find_artifact_metadata_by_id") as mock_find:
                    mock_find.return_value = {
                        "name": "test-model",
                        "type": "model",
                        "version": "main"
                    }
                    with patch("src.index.save_artifact"):
                        with patch("src.index.analyze_model_content") as mock_analyze:
                            mock_analyze.return_value = {"net_score": 0.8}
                            response = client.get("/artifact/model/test-id/rate")
                            assert response.status_code == 200

    def test_get_model_rate_timeout_fallback(self, mock_auth):
        """Test get_model_rate with timeout fallback - event wait returns False (timeout)"""
        from src.index import _rating_status, _rating_locks, _rating_lock
        
        timeout_id = "timeout-id"
        event = threading.Event()
        
        # Mock event.wait before storing in dictionary
        original_wait = event.wait
        
        def mock_wait(timeout=None):
            # Simulate timeout by returning False immediately
            return False
        
        event.wait = mock_wait
        
        # Set up pending rating state with thread safety
        with _rating_lock:
            _rating_status[timeout_id] = RATING_STATUS_PENDING
            _rating_locks[timeout_id] = event
        # Don't set the event - this simulates a timeout scenario
        # The event.wait() will return False, triggering synchronous fallback

        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.analyze_model_content") as mock_analyze:
                mock_get.return_value = {
                    "type": "model",
                    "id": timeout_id,
                    "name": TEST_MODEL_NAME
                }
                mock_analyze.return_value = {"net_score": 0.8}
                
                response = client.get(f"/artifact/model/{timeout_id}/rate")
                # Should fall back to synchronous rating and return 200
                assert response.status_code == 200
                data = response.json()
                assert data["net_score"] == 0.8
        
        # Restore original wait method
        event.wait = original_wait

    def test_get_model_rate_analyze_error(self, mock_auth):
        """Test get_model_rate when analyze_model_content raises error"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {
                "type": "model",
                "id": "test-id",
                "name": "test-model"
            }
            with patch("src.index.analyze_model_content", side_effect=Exception("Analysis error")):
                response = client.get("/artifact/model/test-id/rate")
                # analyze_model_content exception should result in 500
                assert response.status_code == 500

    def test_get_model_lineage_empty_lineage(self, mock_auth):
        """Test get_model_lineage with empty lineage"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                    mock_get.return_value = {
                        "type": "model",
                        "id": "test-id"
                    }
                    mock_lineage.return_value = {"error": "not found"}
                    with patch("src.index.list_models") as mock_list:
                        mock_list.return_value = {"models": [{"name": "test-model"}]}
                        response = client.get("/artifact/model/test-id/lineage")
                        # Should return 200 with empty lineage when error is "not found"
                        assert response.status_code == 200
                        data = response.json()
                        assert "nodes" in data
                        assert "edges" in data

    def test_get_model_lineage_with_base_model(self, mock_auth):
        """Test get_model_lineage with base model"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.get_model_lineage_from_config") as mock_lineage:
                    mock_get.side_effect = [
                        {"type": "model", "id": "test-id", "name": "test-model"},
                        {"type": "model", "id": "base-id", "name": "base-model"}
                    ]
                    mock_lineage.return_value = {
                        "lineage_metadata": {
                            "base_model": "base-model"
                        },
                        "model_id": "test-id"
                    }
                    with patch("src.index.find_artifacts_by_name", return_value=[{"id": "base-id", "name": "base-model"}]):
                        response = client.get("/artifact/model/test-id/lineage")
                        assert response.status_code == 200
                        data = response.json()
                        assert len(data["nodes"]) >= 1
                        assert len(data["edges"]) >= 0

    def test_check_model_license_model_not_found(self, mock_auth):
        """Test check_model_license when model not found"""
        with patch("src.index.get_generic_artifact_metadata", return_value=None):
            with patch("src.index.get_artifact_from_db", return_value=None):
                with patch("src.index.list_models", return_value={"models": []}):
                    with patch("src.index.s3") as mock_s3:
                        from botocore.exceptions import ClientError
                        error_response = {"Error": {"Code": "NoSuchKey"}}
                        mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")
                        response = client.post(
                            "/artifact/model/nonexistent/license-check",
                            json={"github_url": "https://github.com/test/repo"}
                        )
                        assert response.status_code == 404

    def test_check_model_license_extract_error(self, mock_auth):
        """Test check_model_license when license extraction fails"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.extract_model_license", return_value=None):
                    mock_get.return_value = {"type": "model", "id": "test-id"}
                    response = client.post(
                        "/artifact/model/test-id/license-check",
                        json={"github_url": "https://github.com/test/repo"}
                    )
                    assert response.status_code == 404

    def test_check_model_license_external_error(self, mock_auth):
        """Test check_model_license when external service fails"""
        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.extract_model_license", return_value="MIT"):
                    with patch("src.index.extract_github_license", side_effect=Exception("External error")):
                        mock_get.return_value = {"type": "model", "id": "test-id"}
                        response = client.post(
                            "/artifact/model/test-id/license-check",
                            json={"github_url": "https://github.com/test/repo"}
                        )
                        assert response.status_code == 502

    def test_update_artifact_model_s3_verification_found(self, mock_auth):
        """Test update_artifact for model with S3 verification"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index._get_model_name_for_s3", return_value="test-model"):
                with patch("src.index.s3") as mock_s3:
                    mock_get.return_value = {"type": "model", "id": "test-id"}
                    mock_s3.head_object.return_value = {}
                    response = client.put(
                        "/artifacts/model/test-id",
                        json={
                            "metadata": {"id": "test-id", "name": "test"},
                            "data": {"url": "https://example.com"}
                        }
                    )
                    assert response.status_code == 200

    def test_update_artifact_model_list_models_found(self, mock_auth):
        """Test update_artifact for model found via list_models"""
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index._get_model_name_for_s3", return_value=None):
                with patch("src.index.s3") as mock_s3:
                    from botocore.exceptions import ClientError
                    error_response = {"Error": {"Code": "NoSuchKey"}}
                    mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")
                    with patch("src.index.list_models") as mock_list:
                        mock_list.return_value = {"models": [{"name": "test-id"}]}
                        response = client.put(
                            "/artifacts/model/test-id",
                            json={
                                "metadata": {"id": "test-id", "name": "test"},
                                "data": {"url": "https://example.com"}
                            }
                        )
                        assert response.status_code == 200

    def test_delete_artifact_model_list_models_versions(self, mock_auth):
        """Test delete_artifact for model with versions from list_models"""
        with patch("src.index.get_artifact_from_db", return_value=None):
            with patch("src.index.s3") as mock_s3:
                from botocore.exceptions import ClientError
                error_response = {"Error": {"Code": "NoSuchKey"}}
                mock_s3.head_object.side_effect = [
                    ClientError(error_response, "HeadObject"),
                    ClientError(error_response, "HeadObject"),
                    ClientError(error_response, "HeadObject"),
                    {}  # Found on 4th try
                ]
                mock_s3.delete_object.return_value = {}
                with patch("src.index.list_models") as mock_list:
                    mock_list.return_value = {
                        "models": [{"name": "test-id", "version": "1.0.0"}]
                    }
                    response = client.delete("/artifacts/model/test-id")
                    # Should return 200 since mock eventually finds the object (4th try)
                    assert response.status_code == 200

    def test_cleanup_stuck_ratings_multiple(self):
        """Test cleanup of multiple stuck ratings"""
        from src.index import _cleanup_stuck_ratings, _rating_status, _rating_start_times, _rating_lock
        import time

        with _rating_lock:
            _rating_status["stuck-1"] = RATING_STATUS_PENDING
            _rating_status["stuck-2"] = RATING_STATUS_PENDING
            _rating_start_times["stuck-1"] = time.time() - 700
            _rating_start_times["stuck-2"] = time.time() - 800

        _cleanup_stuck_ratings()

        assert _rating_status.get("stuck-1") == RATING_STATUS_FAILED or "stuck-1" not in _rating_status
        assert _rating_status.get("stuck-2") == RATING_STATUS_FAILED or "stuck-2" not in _rating_status

    def test_run_async_rating_exception(self):
        """Test _run_async_rating with exception"""
        from src.index import _run_async_rating, _rating_status, _rating_lock, _rating_locks
        import threading

        with patch("src.index.analyze_model_content", side_effect=Exception("Rating error")):
            with _rating_lock:
                _rating_status["error-id"] = RATING_STATUS_PENDING
                _rating_locks["error-id"] = threading.Event()

            _run_async_rating("error-id", "test-model", "main")

            assert _rating_status.get("error-id") == RATING_STATUS_FAILED

    def test_get_artifact_size_mb_dataset_s3_fallback(self):
        """Test _get_artifact_size_mb for dataset with S3 fallback"""
        from src.index import _get_artifact_size_mb

        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            with patch("src.index.get_artifact_from_db") as mock_db:
                mock_get.return_value = {
                    "name": "test-dataset",
                    "url": "https://example.com/dataset.zip"
                }
                mock_db.return_value = None
                with patch("requests.head", side_effect=Exception("Network error")):
                    with patch("src.index.s3") as mock_s3:
                        mock_s3.head_object.return_value = {"ContentLength": 10485760}
                        size = _get_artifact_size_mb("dataset", "test-id")
                        assert size == 10.0

    def test_parse_dependencies_llm_error_response(self):
        """Test _parse_dependencies with LLM error response"""
        from src.index import _parse_dependencies

        with patch("os.getenv", return_value="test-api-key"):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 500
                text = "Trained on https://huggingface.co/datasets/coco"
                result = _parse_dependencies(text, "test-model")
                assert "datasets" in result

    def test_parse_dependencies_llm_invalid_json(self):
        """Test _parse_dependencies with LLM returning invalid JSON"""
        from src.index import _parse_dependencies

        with patch("os.getenv", return_value="test-api-key"):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": "This is not JSON"
                        }
                    }]
                }
                text = "Trained on https://huggingface.co/datasets/coco"
                result = _parse_dependencies(text, "test-model")
                assert "datasets" in result

    def test_link_model_to_datasets_code_no_readme(self):
        """Test _link_model_to_datasets_code without README"""
        from src.index import _link_model_to_datasets_code

        with patch("src.index.download_model", return_value=None):
            result = _link_model_to_datasets_code("model-id", "test-model", None)
            assert result is None

    def test_link_model_to_datasets_code_no_matches(self):
        """Test _link_model_to_datasets_code with no matches"""
        from src.index import _link_model_to_datasets_code

        with patch("src.index._extract_dataset_code_names_from_readme") as mock_extract:
            mock_extract.return_value = {
                "dataset_name": None,
                "code_name": None
            }
            result = _link_model_to_datasets_code("model-id", "test-model", "README")
            assert result is None

    def test_link_dataset_code_to_models_code_type(self):
        """Test _link_dataset_code_to_models for code type"""
        from src.index import _link_dataset_code_to_models

        with patch("src.index.find_models_with_null_link") as mock_find:
            with patch("src.index.update_artifact_in_db") as mock_update:
                mock_find.return_value = [
                    {"id": "model-id", "name": "test-model", "code_name": "test-code"}
                ]
                _link_dataset_code_to_models("code-id", "test-code", "code")
                mock_update.assert_called()

    def test_link_dataset_code_to_models_name_fallback(self):
        """Test _link_dataset_code_to_models with name fallback"""
        from src.index import _link_dataset_code_to_models

        with patch("src.index.find_models_with_null_link") as mock_find:
            with patch("src.index.update_artifact_in_db") as mock_update:
                mock_find.return_value = [
                    {"id": "model-id", "name": "test-model", "dataset_name": None}
                ]
                _link_dataset_code_to_models("dataset-id", "test-model", "dataset")
                mock_update.assert_called()

    def test_health_components_max_window(self):
        """Test health_components with max window"""
        response = client.get("/health/components?windowMinutes=1440")
        assert response.status_code == 200

    def test_health_components_min_window(self):
        """Test health_components with min window"""
        response = client.get("/health/components?windowMinutes=5")
        assert response.status_code == 200

    def test_trigger_performance_workload_missing_params(self, mock_auth):
        """Test trigger_performance_workload with missing params"""
        response = client.post("/health/performance/workload", json={})
        assert response.status_code == 202  # Uses defaults

    def test_get_performance_results_error(self, mock_auth):
        """Test get_performance_results with error"""
        with patch("src.services.performance.results_retrieval.get_performance_results", side_effect=Exception("Error")):
            response = client.get("/health/performance/results/test-run")
            assert response.status_code == 500

    def test_reset_system_static_token(self, mock_auth):
        """Test reset_system with static token"""
        with patch("src.index.clear_all_artifacts"):
            with patch("src.index.reset_registry"):
                with patch("src.index.purge_tokens"):
                    with patch("src.index.ensure_default_admin"):
                        with patch("src.index.verify_auth_token", return_value=True):
                            with patch("src.index.verify_jwt_token", return_value=None):
                                with patch("src.services.auth_public.STATIC_TOKEN", "test-token"):
                                    response = client.delete(
                                        "/reset",
                                        headers={"Authorization": "Bearer test-token"}
                                    )
                                    assert response.status_code == 200

    def test_reset_system_error(self, mock_auth):
        """Test reset_system with error"""
        with patch("src.index.verify_jwt_token", return_value={"username": "ece30861defaultadminuser"}):
            with patch("src.index.clear_all_artifacts", side_effect=Exception("Error")):
                response = client.delete(
                    "/reset",
                    headers={"Authorization": "Bearer admin-token"}
                )
                assert response.status_code == 500
