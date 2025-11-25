"""
Coverage Gap Fillers for s3_service.py
Targeting specific uncovered lines and error conditions
"""
import pytest
from unittest.mock import MagicMock, patch, ANY
from botocore.exceptions import ClientError
from fastapi import HTTPException
from src.services.s3_service import (
    list_models,
    upload_model,
    download_model,
    model_ingestion,
    get_model_lineage_from_config,
    store_artifact_metadata,
    find_artifact_metadata_by_id,
    list_artifacts_from_s3,
    reset_registry
)

class TestS3ServiceCoverageGaps:
    
    @patch("src.services.s3_service.s3")
    def test_list_models_client_error(self, mock_s3):
        """Test list_models handling ClientError"""
        mock_s3.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "ListObjectsV2"
        )
        
        with pytest.raises(HTTPException) as exc:
            list_models()
        assert exc.value.status_code == 500

    @patch("src.services.s3_service.s3")
    def test_upload_model_client_error(self, mock_s3):
        """Test upload_model handling ClientError"""
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "EntityTooLarge", "Message": "Your proposed upload exceeds the maximum allowed object size."}},
            "PutObject"
        )
        
        with pytest.raises(HTTPException) as exc:
            upload_model("test-model", b"data", "1.0.0")
        assert exc.value.status_code == 500

    @patch("src.services.s3_service.s3")
    def test_download_model_client_error(self, mock_s3):
        """Test download_model handling ClientError"""
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
            "GetObject"
        )
        
        with pytest.raises(HTTPException) as exc:
            download_model("test-model", "1.0.0")
        assert exc.value.status_code == 500

    @patch("src.services.s3_service.s3")
    def test_model_ingestion_s3_upload_fail(self, mock_s3):
        """Test model ingestion failure during S3 upload"""
        mock_s3.put_object.side_effect = Exception("S3 Upload Failed")
        
        result = model_ingestion("https://huggingface.co/test/model")
        assert result["status"] == "error"
        assert "S3 Upload Failed" in result["message"]

    @patch("src.services.s3_service.download_model")
    def test_lineage_invalid_json(self, mock_download):
        """Test lineage extraction with invalid JSON config"""
        mock_download.return_value = b"invalid json content"
        
        with pytest.raises(HTTPException) as exc:
            get_model_lineage_from_config("model1", "1.0.0")
        assert exc.value.status_code == 500

    @patch("src.services.s3_service.s3")
    def test_store_metadata_client_error(self, mock_s3):
        """Test store_artifact_metadata handling ClientError"""
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "We encountered an internal error. Please try again."}},
            "PutObject"
        )
        
        result = store_artifact_metadata("a1", {"key": "value"})
        assert result is False

    @patch("src.services.s3_service.s3")
    def test_find_metadata_client_error(self, mock_s3):
        """Test find_artifact_metadata_by_id handling ClientError"""
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "GetObject"
        )
        
        result = find_artifact_metadata_by_id("a1")
        assert result is None

    @patch("src.services.s3_service.s3")
    def test_list_artifacts_client_error(self, mock_s3):
        """Test list_artifacts_from_s3 handling ClientError"""
        mock_s3.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "InvalidBucketName", "Message": "The specified bucket is not valid."}},
            "ListObjectsV2"
        )
        
        result = list_artifacts_from_s3()
        assert result == []

    @patch("src.services.s3_service.s3")
    def test_reset_registry_partial_failure(self, mock_s3):
        """Test reset_registry with partial deletion failure"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Key": "obj1"}, {"Key": "obj2"}]
        }
        # Fail on delete_objects
        mock_s3.delete_objects.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "DeleteObjects"
        )
        
        with pytest.raises(HTTPException) as exc:
            reset_registry()
        assert exc.value.status_code == 500

    @patch("src.services.s3_service.s3")
    def test_list_models_empty_bucket(self, mock_s3):
        """Test list_models with empty bucket"""
        mock_s3.list_objects_v2.return_value = {}
        
        result = list_models()
        assert result["models"] == []

    @patch("src.services.s3_service.s3")
    def test_list_models_truncated(self, mock_s3):
        """Test list_models with truncated results (pagination)"""
        mock_s3.list_objects_v2.return_value = {
            "IsTruncated": True,
            "NextContinuationToken": "token123",
            "Contents": [{"Key": "models/m1/1.0.0/model.zip"}]
        }
        
        result = list_models()
        assert result["next_token"] == "token123"
        assert len(result["models"]) == 1

    def test_model_ingestion_invalid_url(self):
        """Test model ingestion with invalid URL format"""
        result = model_ingestion("invalid-url")
        assert result["status"] == "error"
        assert "Invalid URL" in result["message"]

    @patch("src.services.s3_service.requests")
    def test_model_ingestion_hf_api_error(self, mock_requests):
        """Test model ingestion with HuggingFace API error"""
        mock_requests.get.return_value.status_code = 404
        
        result = model_ingestion("https://huggingface.co/nonexistent/model")
        assert result["status"] == "error"
        assert "Failed to fetch" in result["message"]
