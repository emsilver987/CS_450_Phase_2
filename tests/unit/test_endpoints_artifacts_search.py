"""
Tests for Artifacts Search endpoints/features
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



class TestListArtifactsS3MetadataLookup:
    """Test S3 metadata lookup in list_artifacts"""

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    @patch("src.index.save_artifact")
    def test_list_artifacts_s3_metadata_fallback(
        self, mock_save, mock_s3, mock_list_all, mock_list_models, mock_auth
    ):
        """Test list_artifacts with S3 metadata lookup"""
        mock_auth.return_value = True
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "main", "id": "model-id"}]
        }
        mock_list_all.return_value = []

        # Mock S3 metadata response
        mock_response = MagicMock()
        mock_response.read.return_value.decode.return_value = '{"artifact_id": "s3-artifact-id", "url": "https://huggingface.co/test-model"}'
        mock_s3.get_object.return_value = {"Body": mock_response}

        response = client.post(
            "/artifacts",
            json=[{"name": "test-model"}],
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_list_artifacts_s3_metadata_no_such_key(
        self, mock_s3, mock_list_all, mock_list_models, mock_auth
    ):
        """Test list_artifacts handles NoSuchKey error in S3"""
        from botocore.exceptions import ClientError

        mock_auth.return_value = True
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "main"}]
        }
        mock_list_all.return_value = []

        # Mock NoSuchKey error
        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

        response = client.post(
            "/artifacts",
            json=[{"name": "test-model"}],
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_list_artifacts_s3_metadata_other_error(
        self, mock_s3, mock_list_all, mock_list_models, mock_auth
    ):
        """Test list_artifacts handles other S3 errors"""
        from botocore.exceptions import ClientError

        mock_auth.return_value = True
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "main"}]
        }
        mock_list_all.return_value = []

        # Mock other S3 error
        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

        response = client.post(
            "/artifacts",
            json=[{"name": "test-model"}],
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200



class TestSearchArtifactsByRegexS3Lookup:
    """Test S3 lookup in search_artifacts_by_regex"""

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_search_artifacts_dataset_s3_metadata(
        self, mock_s3, mock_list_all, mock_list_s3, mock_auth
    ):
        """Test search_artifacts_by_regex with dataset S3 metadata lookup"""
        mock_auth.return_value = True
        mock_list_s3.return_value = {
            "artifacts": [{"name": "test-dataset", "version": "main"}]
        }
        mock_list_all.return_value = []

        # Mock S3 metadata response
        mock_response = MagicMock()
        mock_response.read.return_value.decode.return_value = '{"artifact_id": "dataset-id", "name": "test-dataset"}'
        mock_s3.get_object.return_value = {"Body": mock_response}

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_search_artifacts_code_s3_metadata(
        self, mock_s3, mock_list_all, mock_list_s3, mock_auth
    ):
        """Test search_artifacts_by_regex with code S3 metadata lookup"""
        mock_auth.return_value = True
        mock_list_s3.return_value = {
            "artifacts": [{"name": "test-code", "version": "main"}]
        }
        mock_list_all.return_value = []

        # Mock S3 metadata response
        mock_response = MagicMock()
        mock_response.read.return_value.decode.return_value = '{"artifact_id": "code-id", "name": "test-code"}'
        mock_s3.get_object.return_value = {"Body": mock_response}

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_search_artifacts_code_s3_exception(
        self, mock_s3, mock_list_all, mock_list_s3, mock_auth
    ):
        """Test search_artifacts_by_regex handles S3 exceptions for code"""
        mock_auth.return_value = True
        mock_list_s3.return_value = {
            "artifacts": [{"name": "test-code", "version": "main"}]
        }
        mock_list_all.return_value = []

        # Mock S3 exception
        mock_s3.get_object.side_effect = Exception("S3 error")

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_search_artifacts_dataset_fallback_to_db(
        self, mock_s3, mock_list_all, mock_list_s3, mock_auth
    ):
        """Test search_artifacts_by_regex falls back to database for datasets"""
        mock_auth.return_value = True
        mock_list_s3.return_value = {
            "artifacts": [{"name": "test-dataset", "version": "main"}]
        }
        mock_list_all.return_value = [
            {"id": "db-dataset-id", "name": "test-dataset", "type": "dataset"}
        ]

        # Mock S3 exception
        mock_s3.get_object.side_effect = Exception("S3 error")

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200



class TestSearchArtifactsStorageVerification:
    """Test artifact verification in search_artifacts_by_regex"""

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.list_models")
    @patch("src.index.s3")
    def test_search_artifacts_verify_model_in_s3(
        self, mock_s3, mock_list_models, mock_list_all, mock_auth
    ):
        """Test search_artifacts_by_regex verifies model exists in S3"""
        mock_auth.return_value = True
        mock_list_all.return_value = [
            {"id": "model-id", "name": "test-model", "type": "model"}
        ]
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "main"}]
        }
        mock_s3.head_object.return_value = {}  # Model exists

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.list_models")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.s3")
    def test_search_artifacts_model_not_in_s3(
        self, mock_s3, mock_list_s3, mock_list_models, mock_list_all, mock_auth
    ):
        """Test search_artifacts_by_regex skips model not in S3"""
        from botocore.exceptions import ClientError

        mock_auth.return_value = True
        mock_list_all.return_value = [
            {"id": "model-id", "name": "test-model", "type": "model"}
        ]
        mock_list_models.return_value = {"models": []}
        mock_list_s3.return_value = {"artifacts": []}
        # Mock head_object to raise error (model not found)
        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        # Should return 404 if no artifacts found, or 200 if other artifacts found
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.s3")
    def test_search_artifacts_verify_dataset_in_s3(
        self, mock_s3, mock_list_s3, mock_list_all, mock_auth
    ):
        """Test search_artifacts_by_regex verifies dataset exists in S3"""
        mock_auth.return_value = True
        mock_list_all.return_value = [
            {"id": "dataset-id", "name": "test-dataset", "type": "dataset", "version": "main"}
        ]
        mock_list_s3.return_value = {"artifacts": []}
        mock_s3.head_object.return_value = {}  # Dataset exists

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.list_models")
    @patch("src.index.list_artifacts_from_s3")
    @patch("src.index.s3")
    def test_search_artifacts_long_name_skip(
        self, mock_s3, mock_list_s3, mock_list_models, mock_list_all, mock_auth
    ):
        """Test search_artifacts_by_regex skips very long names"""
        mock_auth.return_value = True
        long_name = "a" * 1001  # Over 1000 characters
        mock_list_all.return_value = [
            {"id": "test-id", "name": long_name, "type": "model"}
        ]
        mock_list_models.return_value = {"models": []}
        mock_list_s3.return_value = {"artifacts": []}

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "a"},
            headers={"Authorization": "Bearer token"}
        )
        # Should return 404 if no artifacts found (long name skipped)
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    @patch("src.index.s3")
    def test_search_artifacts_regex_error(
        self, mock_s3, mock_list_all, mock_auth
    ):
        """Test search_artifacts_by_regex handles regex errors"""
        mock_auth.return_value = True
        mock_list_all.return_value = [
            {"id": "test-id", "name": "test[", "type": "model"}  # Invalid regex
        ]

        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test["},
            headers={"Authorization": "Bearer token"}
        )
        # Should handle regex error gracefully
        assert response.status_code in [200, 400]



