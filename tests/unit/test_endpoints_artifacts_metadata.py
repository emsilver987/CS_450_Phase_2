"""
Tests for Artifacts Metadata endpoints/features
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



class TestGetArtifactSizeExceptionHandling:
    """Test exception handling in _get_artifact_size_mb"""

    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.s3")
    def test_get_artifact_size_exception(self, mock_s3, mock_get_meta):
        """Test _get_artifact_size_mb handles exceptions"""
        from src.index import _get_artifact_size_mb

        mock_get_meta.return_value = {"type": "dataset", "id": "test-id"}
        mock_s3.head_object.side_effect = Exception("S3 error")

        result = _get_artifact_size_mb("dataset", "test-id")
        assert result == 0.0



class TestGetModelNameForS3ExceptionHandling:
    """Test exception handling in _get_model_name_for_s3"""

    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    def test_get_model_name_exception(self, mock_get_db, mock_get_meta):
        """Test _get_model_name_for_s3 handles exceptions"""
        from src.index import _get_model_name_for_s3

        mock_get_meta.side_effect = Exception("Database error")
        mock_get_db.side_effect = Exception("Database error")

        result = _get_model_name_for_s3("test-id")
        assert result is None



