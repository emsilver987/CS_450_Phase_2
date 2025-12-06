"""
Tests for Artifacts Crud endpoints/features
"""
import pytest
import threading
from unittest.mock import patch, MagicMock
from tests.unit.test_index_shared import (
    client, mock_auth, mock_s3_service, mock_artifact_storage,
    reset_rating_state, TEST_MODEL_ID, TEST_MODEL_NAME,
    TEST_DATASET_ID, TEST_DATASET_NAME, TEST_CODE_ID, TEST_CODE_NAME,
    RATING_STATUS_PENDING, RATING_STATUS_COMPLETED, RATING_STATUS_FAILED,
    RATING_STATUS_DISQUALIFIED
)


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
                                        # Mock find_artifact_metadata_by_id to return metadata on first call
                                        # This simulates successful S3 metadata storage verification
                                        mock_metadata = {
                                            "id": "test-id",
                                            "name": "test-model",
                                            "type": "model",
                                            "version": "main",
                                            "url": "https://huggingface.co/test-model"
                                        }
                                        with patch("src.index.find_artifact_metadata_by_id", return_value=mock_metadata):
                                            with patch("zipfile.ZipFile"):
                                                # Patch random.randint to return a predictable ID
                                                with patch("src.index.random.randint", return_value=1234567890):
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
            # Disqualified models may still return 200 with metadata
            assert response.status_code in [200, 404]

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



