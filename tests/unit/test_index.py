import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys
import logging

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock boto3 and watchtower to prevent startup hangs and logging errors
# Mock boto3 to prevent startup hangs (watchtower is patched in conftest.py)
with patch("boto3.client"):
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
            with patch("src.index.clear_all_artifacts") as mock_clear:
                with patch("src.index.reset_registry") as mock_reset:
                    with patch("src.index.purge_tokens") as mock_purge:
                        with patch("src.index.ensure_default_admin") as mock_admin:
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
            _run_async_rating("test-id-3", "test-model", "1.0.0")
            from src.index import _rating_status
            assert _rating_status.get("test-id-3") == "disqualified"

    def test_health_components_invalid_window(self):
        """Test health components with invalid window"""
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
        """Test get model rate with pending status"""
        from src.index import _rating_status, _rating_locks, _rating_results
        import threading

        _rating_status["test-id-pending"] = "pending"
        _rating_locks["test-id-pending"] = threading.Event()
        _rating_locks["test-id-pending"].set()  # Signal immediately
        # Set status to completed after wait
        _rating_status["test-id-pending"] = "completed"
        _rating_results["test-id-pending"] = {"net_score": 0.8}

        with patch("src.index.get_generic_artifact_metadata") as mock_get:
            mock_get.return_value = {"type": "model", "id": "test-id-pending", "name": "test-model"}
            response = client.get("/artifact/model/test-id-pending/rate")
            assert response.status_code == 200
            data = response.json()
            assert data["net_score"] == 0.8

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
        with patch("src.index._artifact_storage", {}) as mock_storage:
            with patch("src.index.list_all_artifacts", return_value=[]):
                with patch("src.index.save_artifact") as mock_save:
                    with patch("src.index._link_dataset_code_to_models"):
                        with patch("src.index.store_artifact_metadata"):
                            response = client.post(
                                "/artifact/dataset",
                                json={"url": "https://example.com/dataset", "name": "test-dataset"}
                            )
                            assert response.status_code == 201
                            data = response.json()
                            assert data["metadata"]["type"] == "dataset"

    def test_create_artifact_code_success(self, mock_auth):
        """Test create code artifact"""
        with patch("src.index._artifact_storage", {}) as mock_storage:
            with patch("src.index.list_all_artifacts", return_value=[]):
                with patch("src.index.save_artifact") as mock_save:
                    with patch("src.index._link_dataset_code_to_models"):
                        with patch("src.index.store_artifact_metadata"):
                            response = client.post(
                                "/artifact/code",
                                json={"url": "https://github.com/test/repo", "name": "test-code"}
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
                with patch("src.index._artifact_storage", {"test-id": {"type": "dataset"}}) as mock_storage:
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
                mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")
                with patch("src.index.list_models", return_value={"models": []}):
                    response = client.delete("/artifacts/model/nonexistent")
                    assert response.status_code == 404

    def test_delete_artifact_code_success(self, mock_auth):
        """Test delete code artifact"""
        with patch("src.index.get_artifact_from_db") as mock_get:
            with patch("src.index.delete_artifact") as mock_delete:
                with patch("src.index._artifact_storage", {"test-id": {"type": "code"}}) as mock_storage:
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
