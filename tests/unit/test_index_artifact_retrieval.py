"""
Coverage tests for index.py artifact retrieval logic
Targeting complex fallback mechanisms and rating status handling
"""
import pytest
import threading
import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.index import app

client = TestClient(app)

class TestArtifactRetrievalCoverage:
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    def test_get_artifact_db_hit(self, mock_get_db, mock_get_meta, mock_verify):
        """Test artifact found in DB via get_generic_artifact_metadata"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {
            "id": "m1",
            "name": "model1",
            "type": "model",
            "version": "1.0.0",
            "url": "https://huggingface.co/model1"
        }
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["Name"] == "model1"

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    def test_get_artifact_db_fallback_hit(self, mock_get_db, mock_get_meta, mock_verify):
        """Test artifact found in DB via fallback get_artifact_from_db"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = {
            "id": "m1",
            "name": "model1",
            "type": "model",
            "version": "1.0.0"
        }
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["Name"] == "model1"

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    def test_get_artifact_type_mismatch_db(self, mock_get_db, mock_get_meta, mock_verify):
        """Test artifact found in DB but wrong type"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {
            "id": "d1",
            "name": "dataset1",
            "type": "dataset" # Mismatch
        }
        
        # Should fall through to S3 lookup logic
        with patch("src.index.find_artifact_metadata_by_id") as mock_s3:
            mock_s3.return_value = None
            with patch("src.index.list_models") as mock_list:
                mock_list.return_value = {"models": []}
                response = client.get("/artifact/model/d1")
                assert response.status_code == 404

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.find_artifact_metadata_by_id")
    @patch("src.index.save_artifact")
    def test_get_artifact_s3_metadata_hit(self, mock_save, mock_s3, mock_get_db, mock_get_meta, mock_verify):
        """Test artifact found in S3 metadata (not in DB)"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_s3.return_value = {
            "id": "m1",
            "name": "model1",
            "type": "model",
            "version": "1.0.0",
            "url": "https://huggingface.co/model1"
        }
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["Name"] == "model1"
        # Verify it was restored to DB
        mock_save.assert_called_once()

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.find_artifact_metadata_by_id")
    def test_get_artifact_s3_type_mismatch(self, mock_s3, mock_get_db, mock_get_meta, mock_verify):
        """Test artifact found in S3 metadata but wrong type"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_s3.return_value = {
            "id": "d1",
            "type": "dataset" # Mismatch
        }
        
        with patch("src.index.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            response = client.get("/artifact/model/d1")
            assert response.status_code == 404

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.find_artifact_metadata_by_id")
    @patch("src.index.list_models")
    def test_get_artifact_fallback_list_models(self, mock_list, mock_s3, mock_get_db, mock_get_meta, mock_verify):
        """Test artifact found via list_models fallback"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_s3.return_value = None
        
        # Mock list_models finding the model
        mock_list.return_value = {
            "models": [
                {"name": "model1", "version": "1.0.0"}
            ]
        }
        
        response = client.get("/artifact/model/model1")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["Name"] == "model1"

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    def test_rating_status_pending_success(self, mock_get_meta, mock_verify):
        """Test waiting for pending rating that succeeds"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {"id": "m1", "type": "model", "name": "model1"}
        
        # Inject pending status and lock
        from src.index import _rating_status, _rating_locks
        _rating_status["m1"] = "pending"
        event = threading.Event()
        _rating_locks["m1"] = event
        
        # Start a thread to complete the rating after a short delay
        def complete_rating():
            time.sleep(0.1)
            _rating_status["m1"] = "completed"
            event.set()
            
        threading.Thread(target=complete_rating).start()
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 200
        
        # Cleanup
        if "m1" in _rating_status: del _rating_status["m1"]
        if "m1" in _rating_locks: del _rating_locks["m1"]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    def test_rating_status_failed(self, mock_get_meta, mock_verify):
        """Test artifact with failed rating status"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {"id": "m1", "type": "model"}
        
        # Inject failed status
        from src.index import _rating_status
        _rating_status["m1"] = "failed"
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 404
        
        # Cleanup
        if "m1" in _rating_status: del _rating_status["m1"]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    def test_rating_status_disqualified(self, mock_get_meta, mock_verify):
        """Test artifact with disqualified rating status"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {"id": "m1", "type": "model"}
        
        # Inject disqualified status
        from src.index import _rating_status
        _rating_status["m1"] = "disqualified"
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 404
        
        # Cleanup
        if "m1" in _rating_status: del _rating_status["m1"]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    def test_rating_status_timeout(self, mock_get_meta, mock_verify):
        """Test timeout waiting for pending rating"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {"id": "m1", "type": "model"}
        
        # Inject pending status and lock
        from src.index import _rating_status, _rating_locks
        _rating_status["m1"] = "pending"
        event = MagicMock()
        event.wait.return_value = False # Simulate timeout
        _rating_locks["m1"] = event
        
        response = client.get("/artifact/model/m1")
        assert response.status_code == 404
        
        # Cleanup
        if "m1" in _rating_status: del _rating_status["m1"]
        if "m1" in _rating_locks: del _rating_locks["m1"]
