import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request
import json

# Import the functions to test
# Note: We need to patch dependencies before importing if they have side effects, 
# but here we can patch where they are used.
from src.index import post_artifact_ingest, create_artifact_by_type

@pytest.mark.asyncio
async def test_ingest_logging():
    # Mock Request
    request = MagicMock(spec=Request)
    request.headers = {"content-type": "application/x-www-form-urlencoded"}
    
    # Mock form data
    async def mock_form():
        return {
            "name": "test-model-ingest",
            "version": "1.0.0",
            "type": "model"
        }
    request.form = mock_form
    
    # Mock dependencies
    with patch("src.index.verify_auth_token", return_value=True), \
         patch("src.index.get_user_id_from_request", return_value="test-user-1"), \
         patch("src.index.log_upload_event") as mock_log, \
         patch("src.index.model_ingestion"), \
         patch("src.index.save_artifact"), \
         patch("src.index.store_artifact_metadata"), \
         patch("src.index.list_models", return_value={"models": []}), \
         patch("src.index._rating_status", {}), \
         patch("src.index._rating_locks", {}), \
         patch("src.index.threading.Thread"), \
         patch("src.index.get_artifact_from_db", return_value={"id": "123"}):
        
        # Execute
        await post_artifact_ingest(request)
        
        # Verify log_upload_event was called
        mock_log.assert_called_once()
        call_args = mock_log.call_args[1]
        assert call_args["artifact_name"] == "test-model-ingest"
        assert call_args["artifact_type"] == "model"
        assert call_args["user_id"] == "test-user-1"
        assert call_args["status"] == "success"
        print("\n✅ test_ingest_logging passed: log_upload_event called correctly")

@pytest.mark.asyncio
async def test_create_artifact_logging():
    # Mock Request
    request = MagicMock(spec=Request)
    request.headers = {"content-type": "application/json"}
    
    # Mock json body
    async def mock_json():
        return {
            "url": "https://huggingface.co/test-org/test-model-create",
            "version": "2.0.0"
        }
    request.json = mock_json
    
    # Mock dependencies
    with patch("src.index.verify_auth_token", return_value=True), \
         patch("src.index.get_user_id_from_request", return_value="test-user-2"), \
         patch("src.index.log_upload_event") as mock_log, \
         patch("src.index.model_ingestion"), \
         patch("src.index.save_artifact"), \
         patch("src.index.store_artifact_metadata"), \
         patch("src.index.list_models", return_value={"models": []}), \
         patch("src.index._rating_status", {}), \
         patch("src.index._rating_locks", {}), \
         patch("src.index.threading.Thread"):
        
        # Execute
        await create_artifact_by_type("model", request)
        
        # Verify log_upload_event was called
        mock_log.assert_called_once()
        call_args = mock_log.call_args[1]
        assert call_args["artifact_name"] == "test-org/test-model-create"
        assert call_args["artifact_type"] == "model"
        assert call_args["user_id"] == "test-user-2"
        assert call_args["status"] == "success"
        print("\n✅ test_create_artifact_logging passed: log_upload_event called correctly")
