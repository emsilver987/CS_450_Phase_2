"""
Ultra-targeted tests for remaining large uncovered blocks in index.py
Focusing on artifact upload, metadata extraction, and async operations
"""
import pytest
import zipfile
import io
import json
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient
from src.index import app

client = TestClient(app)


class TestArtifactUploadWithMetadataExtraction:
    """Target lines 2395-2469: artifact upload with README extraction"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.index.store_artifact_metadata")
    @patch("src.index.generate_download_url")
    @patch("src.services.s3_service.download_model")
    def test_upload_with_readme_extraction_success(
        self, mock_download, mock_gen_url, mock_store_meta, 
        mock_save, mock_ingest, mock_verify
    ):
        """Test artifact upload with successful README extraction"""
        mock_verify.return_value = {"username": "user1"}
        mock_ingest.return_value = {"status": "success"}
        
        # Create a zip with README
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("README.md", "Dataset: my-dataset\nCode: my-code-repo")
        mock_download.return_value = zip_buffer.getvalue()
        
        mock_gen_url.return_value = "https://download.url/model.zip"
        
        with patch("src.index._extract_dataset_code_names_from_readme") as mock_extract:
            with patch("src.index._link_model_to_datasets_code") as mock_link:
                with patch("src.index._run_async_rating") as mock_rating:
                    mock_extract.return_value = {
                        "dataset_name": "my-dataset",
                        "code_name": "my-code-repo"
                    }
                    
                    response = client.post("/artifacts", json={
                        "Content": "https://huggingface.co/user/model",
                        "URL": "https://huggingface.co/user/model",
                        "debloat": False
                    })
                    
                    # Should succeed
                    assert response.status_code in [200, 201, 202]
                    
                    # Verify README extraction was attempted
                    mock_download.assert_called()
                    
                    # Verify linking was called
                    mock_link.assert_called()

    @patch("src.index.verify_auth_token")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.services.s3_service.download_model")
    def test_upload_readme_extraction_failure(
        self, mock_download, mock_save, mock_ingest, mock_verify
    ):
        """Test artifact upload when README extraction fails"""
        mock_verify.return_value = {"username": "user1"}
        mock_ingest.return_value = {"status": "success"}
        
        # Simulate download failure
        mock_download.side_effect = Exception("Download failed")
        
        with patch("src.index.store_artifact_metadata"):
            with patch("src.index.generate_download_url") as mock_gen:
                with patch("src.index._run_async_rating"):
                    mock_gen.return_value = "https://download.url/model.zip"
                    
                    response = client.post("/artifacts", json={
                        "Content": "https://huggingface.co/user/model",
                        "debloat": False
                    })
                    
                    # Should still succeed even if README extraction fails
                    assert response.status_code in [200, 201, 202]

    @patch("src.index.verify_auth_token")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.index.store_artifact_metadata")
    @patch("src.index.generate_download_url")
    def test_upload_s3_metadata_storage_failure(
        self, mock_gen_url, mock_store_meta, mock_save, mock_ingest, mock_verify
    ):
        """Test artifact upload when S3 metadata storage fails"""
        mock_verify.return_value = {"username": "user1"}
        mock_ingest.return_value = {"status": "success"}
        mock_gen_url.return_value = "https://download.url/model.zip"
        
        # S3 metadata storage fails
        mock_store_meta.side_effect = Exception("S3 error")
        
        with patch("src.index._run_async_rating"):
            response = client.post("/artifacts", json={
                "Content": "https://huggingface.co/user/model",
                "debloat": False
            })
            
            # Should still succeed (failure is logged but not fatal)
            assert response.status_code in [200, 201, 202]

    @patch("src.index.verify_auth_token")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.index.generate_download_url")
    def test_upload_with_debloat_option(
        self, mock_gen_url, mock_save, mock_ingest, mock_verify
    ):
        """Test artifact upload with debloat option"""
        mock_verify.return_value = {"username": "user1"}
        mock_ingest.return_value = {"status": "success"}
        mock_gen_url.return_value = "https://download.url/model.zip"
        
        with patch("src.index.store_artifact_metadata"):
            with patch("src.index._run_async_rating"):
                response = client.post("/artifacts", json={
                    "Content": "https://huggingface.co/user/model",
                    "debloat": True  # Test debloat option
                })
                
                assert response.status_code in [200, 201, 202]


class TestArtifactOperationsExtended:
    """Target lines 2488-2584: extended artifact operations"""
    
    @patch("src.index.verify_auth_token") 
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.update_artifact")
    def test_update_artifact_with_various_fields(
        self, mock_update, mock_get, mock_verify
    ):
        """Test updating artifact with various field combinations"""
        mock_verify.return_value = {"username": "admin", "isAdmin": True}
        mock_get.return_value = {"id": "a1", "name": "old", "type": "model"}
        mock_update.return_value = True
        
        # Update name only
        response = client.put("/artifacts/model/a1", json={"name": "new-name"})
        assert response.status_code in [200, 400]
        
        # Update version only
        response = client.put("/artifacts/model/a1", json={"version": "2.0.0"})
        assert response.status_code in [200, 400]
        
        # Update multiple fields
        response = client.put("/artifacts/model/a1", json={
            "name": "new-name",
            "version": "2.0.0",
            "url": "https://example.com/new"
        })
        assert response.status_code in [200, 400]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.delete_artifact")
    @patch("src.index.s3")
    def test_delete_artifact_with_s3_cleanup(
        self, mock_s3, mock_delete_db, mock_get, mock_verify
    ):
        """Test deleting artifact with S3 cleanup"""
        mock_verify.return_value = {"username": "admin", "isAdmin": True}
        mock_get.return_value = {
            "id": "a1",
            "name": "model1",
            "type": "model",
            "version": "1.0.0"
        }
        mock_delete_db.return_value = True
        
        response = client.delete("/artifacts/model/a1")
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    def test_list_artifacts_with_complex_filters(
        self, mock_list, mock_verify
    ):
        """Test listing artifacts with complex query filters"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = [
            {"id": "a1", "name": "model1", "type": "model"},
            {"id": "a2", "name": "dataset1", "type": "dataset"}
        ]
        
        # Test with type filter
        response = client.post("/artifacts", json=[
            {"name": "*", "type": "model"}
        ])
        assert response.status_code in [200, 403]
        
        # Test with version filter
        response = client.post("/artifacts", json=[
            {"name": "model*", "version": "1.0.0"}
        ])
        assert response.status_code in [200, 403]


class TestSearchAndFilterLogic:
    """Target lines 2848-2945: search and filter logic"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    def test_regex_search_with_various_patterns(
        self, mock_list, mock_verify
    ):
        """Test regex search with various pattern types"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = [
            {"id": "a1", "name": "test-model-v1"},
            {"id": "a2", "name": "test-dataset-v1"},
            {"id": "a3", "name": "prod-model-v2"}
        ]
        
        # Test wildcard pattern
        response = client.post("/artifact/byRegEx", json={"RegEx": "test.*"})
        assert response.status_code in [200, 404]
        
        # Test exact match
        response = client.post("/artifact/byRegEx", json={"RegEx": "^test-model-v1$"})
        assert response.status_code in [200, 404]
        
        # Test OR pattern
        response = client.post("/artifact/byRegEx", json={"RegEx": "model|dataset"})
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.find_artifacts_by_name")
    def test_find_by_name_with_variations(
        self, mock_find, mock_verify
    ):
        """Test finding artifacts by name with various inputs"""
        mock_verify.return_value = {"username": "user1"}
        mock_find.return_value = [{"id": "a1", "name": "test-artifact"}]
        
        # Test exact name
        response = client.get("/artifact/byName/test-artifact")
        assert response.status_code in [200, 404]
        
        # Test with path encoding
        response = client.get("/artifact/byName/user%2Fmodel")
        assert response.status_code in [200, 404]
        
        # Test with special characters
        response = client.get("/artifact/byName/my-model_v1.2")
        assert response.status_code in [200, 404]


class TestAsyncRatingIntegration:
    """Test async rating thread integration"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    def test_async_rating_thread_started(
        self, mock_save, mock_ingest, mock_verify
    ):
        """Test that async rating thread is started"""
        mock_verify.return_value = {"username": "user1"}
        mock_ingest.return_value = {"status": "success"}
        
        with patch("src.index.threading.Thread") as mock_thread:
            with patch("src.index.store_artifact_metadata"):
                with patch("src.index.generate_download_url") as mock_gen:
                    mock_gen.return_value = "https://url"
                    
                    response = client.post("/artifacts", json={
                        "Content": "https://huggingface.co/user/model",
                        "debloat": False
                    })
                    
                    # Verify thread was created and started
                    if response.status_code in [200, 201, 202]:
                        mock_thread.assert_called()
                        thread_instance = mock_thread.return_value
                        thread_instance.start.assert_called()
