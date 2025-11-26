import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys
import logging

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock boto3 and watchtower to prevent startup hangs and logging errors
with patch("boto3.client"), patch("watchtower.CloudWatchLogHandler") as MockHandler:
    # Ensure the mock handler has a valid integer level to prevent TypeError in logging module
    MockHandler.return_value.level = logging.INFO
    from src.index import app

client = TestClient(app)

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

def test_health_components():
    response = client.get("/health/components")
    assert response.status_code == 200
    data = response.json()
    assert "components" in data
    assert data["components"][0]["id"] == "validator-service"

def test_health_components_invalid_window():
    response = client.get("/health/components?windowMinutes=1")
    assert response.status_code == 400

def test_list_artifacts_no_auth():
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
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.get("/artifact/byName/test-model")
            assert response.status_code == 403

    def test_get_artifact_by_name_empty_name(self, mock_auth):
        response = client.get("/artifact/byName/")
        assert response.status_code in [404, 400]

    def test_get_artifact_by_name_found_in_db(self, mock_auth):
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
        with patch("src.index.verify_auth_token", return_value=False):
            response = client.post("/artifact/byRegEx", json={"regex": "test.*"})
            assert response.status_code == 403

    def test_search_by_regex_missing_field(self, mock_auth):
        response = client.post("/artifact/byRegEx", json={})
        assert response.status_code == 400

    def test_search_by_regex_invalid_regex(self, mock_auth):
        response = client.post("/artifact/byRegEx", json={"regex": "[invalid"})
        assert response.status_code == 400

    def test_search_by_regex_redos_detection(self, mock_auth):
        # Test ReDoS pattern detection
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
                            assert response.status_code in [400, 404]

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
                    with patch("src.index.save_artifact") as mock_save:
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
        with patch("src.index.save_artifact") as mock_save:
            with patch("src.index.store_artifact_metadata") as mock_store:
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
        assert response.status_code == 200
        data = response.json()
        assert data["net_score"] == 0.0

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
            with patch("src.index._rating_status", {"test-id": "completed"}):
                with patch("src.index._rating_results", {"test-id": {"net_score": 0.9}}):
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
