"""
Coverage tests for index.py ingestion logic
Targeting complex ingestion workflow, README extraction, and async rating
"""
import pytest
import threading
import time
import zipfile
import io
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.index import app

client = TestClient(app)

class TestIngestLogicCoverage:
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    def test_ingest_duplicate_model(self, mock_list, mock_verify):
        """Test ingestion of already existing model"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = {"models": [{"name": "existing-model"}]}
        
        response = client.post("/artifact/model", json={
            "name": "existing-model",
            "version": "1.0.0"
        })
        assert response.status_code == 409

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.index.get_artifact_from_db")
    @patch("src.services.s3_service.download_model")
    def test_ingest_success_with_readme(self, mock_download, mock_get_db, mock_save, mock_ingest, mock_list, mock_verify):
        """Test successful ingestion with README extraction"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = {"models": []}
        mock_ingest.return_value = {"status": "success"}
        mock_get_db.return_value = {"id": "123", "name": "new-model"}
        
        # Create a fake zip with README
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("README.md", "This model uses dataset: my-dataset and code: my-code")
        mock_download.return_value = zip_buffer.getvalue()
        
        with patch("src.index._run_async_rating") as mock_rating:
            response = client.post("/artifact/model", json={
                "name": "new-model",
                "version": "1.0.0"
            })
            
            assert response.status_code == 201
            # Verify save was called with extracted metadata
            args, _ = mock_save.call_args
            assert "dataset_name" in args[1] or "code_name" in args[1]
            # Verify async rating was started
            mock_rating.assert_called_once()

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.services.s3_service.download_model")
    def test_ingest_readme_extraction_failure(self, mock_download, mock_save, mock_ingest, mock_list, mock_verify):
        """Test ingestion where README extraction fails"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = {"models": []}
        mock_ingest.return_value = {"status": "success"}
        
        # Simulate download failure
        mock_download.side_effect = Exception("Download failed")
        
        with patch("src.index._run_async_rating"):
            response = client.post("/artifact/model", json={
                "name": "new-model",
                "version": "1.0.0"
            })
            
            assert response.status_code == 201
            # Should still succeed, just without extra metadata

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_models")
    @patch("src.index.model_ingestion")
    @patch("src.index.save_artifact")
    @patch("src.index.get_artifact_from_db")
    def test_ingest_save_verification_failure(self, mock_get_db, mock_save, mock_ingest, mock_list, mock_verify):
        """Test ingestion where database save verification fails"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = {"models": []}
        mock_ingest.return_value = {"status": "success"}
        mock_get_db.return_value = None # Verification fails
        
        with patch("src.index._run_async_rating"):
            response = client.post("/artifact/model", json={
                "name": "new-model",
                "version": "1.0.0"
            })
            
            # Should log error but still return 201 as the process started
            assert response.status_code == 201

    @patch("src.index.verify_auth_token")
    def test_ingest_invalid_artifact_type(self, mock_verify):
        """Test ingestion with unsupported artifact type"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post("/artifact/dataset", json={
            "name": "new-dataset",
            "version": "1.0.0"
        })
        assert response.status_code == 501 # Not implemented yet

    @patch("src.index.verify_auth_token")
    def test_ingest_missing_name(self, mock_verify):
        """Test ingestion with missing name"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post("/artifact/model", json={
            "version": "1.0.0"
        })
        assert response.status_code == 400
