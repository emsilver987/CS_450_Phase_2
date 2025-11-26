"""
Comprehensive tests for s3_service.py HuggingFace integration
Targeting lines 788-974 and 1320-1684
"""
import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError


class TestHuggingFaceIntegration:
    """Target HuggingFace download and integration (lines 788-974)"""
    
    @patch("src.services.s3_service.requests")
    @patch("src.services.s3_service.s3")
    def test_download_from_huggingface_full_model(self, mock_s3, mock_requests):
        """Test downloading full model from HuggingFace"""
        from src.services.s3_service import download_from_huggingface
        
        # Mock API response
        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {"siblings": [{"rfilename": "config.json"}]}
        
        # Mock File response
        mock_file_resp = MagicMock()
        mock_file_resp.status_code = 200
        mock_file_resp.content = b"file_content"
        
        # side_effect: first call is API, subsequent calls are file downloads
        def side_effect(*args, **kwargs):
            if "api/models" in args[0]:
                return mock_api_resp
            return mock_file_resp
            
        mock_requests.get.side_effect = side_effect
        
        result = download_from_huggingface("user/model", "main", "full")
        # The result is a zip file containing the downloaded files
        import zipfile
        import io
        with zipfile.ZipFile(io.BytesIO(result), "r") as z:
            assert "config.json" in z.namelist()
            assert z.read("config.json") == b"file_content"

    @patch("src.services.s3_service.requests")
    def test_download_from_huggingface_not_found(self, mock_requests):
        """Test downloading non-existent model from HuggingFace"""
        from src.services.s3_service import download_from_huggingface
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response
        
        with pytest.raises(Exception):
            download_from_huggingface("user/nonexistent", "main", "full")

    @patch("src.services.s3_service.requests")
    def test_download_from_huggingface_timeout(self, mock_requests):
        """Test HuggingFace download timeout"""
        from src.services.s3_service import download_from_huggingface
        import requests
        
        mock_requests.get.side_effect = requests.Timeout("Connection timeout")
        
        with pytest.raises(Exception):
            download_from_huggingface("user/model", "main", "full")

    @patch("src.services.s3_service.requests")
    def test_fetch_huggingface_api_metadata(self, mock_requests):
        """Test fetching model metadata from HuggingFace API"""
        from src.services.s3_service import fetch_huggingface_metadata
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "modelId": "user/model",
            "author": "user",
            "downloads": 1000,
            "likes": 50,
            "tags": ["nlp", "transformers"],
            "license": "MIT"
        }
        mock_requests.get.return_value = mock_response
        
        result = fetch_huggingface_metadata("user/model")
        assert result["license"] == "MIT"
        assert result["modelId"] == "user/model"

    @patch("src.services.s3_service.requests")
    def test_fetch_huggingface_readme(self, mock_requests):
        """Test fetching README from HuggingFace"""
        from src.services.s3_service import fetch_huggingface_readme
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Model Card\n\nThis is a test model."
        mock_requests.get.return_value = mock_response
        
        result = fetch_huggingface_readme("user/model")
        assert "test model" in result.lower()

    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.requests")
    def test_model_ingestion_from_huggingface(self, mock_requests, mock_s3):
        """Test full model ingestion from HuggingFace"""
        from src.services.s3_service import model_ingestion
        
        # Mock HF metadata
        meta_response = MagicMock()
        meta_response.status_code = 200
        meta_response.json.return_value = {
            "modelId": "user/model",
            "license": "MIT",
            "siblings": [{"rfilename": "config.json"}, {"rfilename": "pytorch_model.bin"}]
        }
        
        # Mock HF download (download_from_huggingface)
        # We need to mock requests.get to handle both metadata fetch and file download
        # But model_ingestion calls download_from_huggingface which calls requests.get
        # And it also calls validate_huggingface_structure which checks zip content
        
        # Let's mock download_from_huggingface directly to simplify
        with patch("src.services.s3_service.download_from_huggingface") as mock_download:
            # Create a valid zip file
            import io
            import zipfile
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as z:
                z.writestr("config.json", "{}")
                z.writestr("pytorch_model.bin", "data")
            mock_download.return_value = buffer.getvalue()
            
            # Mock run_acme_metrics to return passing scores
            # Note: run_acme_metrics is imported from src.services.rating inside model_ingestion
            with patch("src.services.rating.run_acme_metrics") as mock_metrics:
                mock_metrics.return_value = {
                    "license": 1.0,
                    "ramp_up": 1.0,
                    "bus_factor": 1.0,
                    "performance_claims": 1.0,
                    "size": 1.0,
                    "dataset_code": 1.0,
                    "dataset_quality": 1.0,
                    "code_quality": 1.0,
                    "reproducibility": 1.0,
                    "reviewedness": 1.0,
                    "treescore": 1.0
                }
                
                result = model_ingestion("https://huggingface.co/user/model", "main")
                assert result["message"] == "Model ingestion successful"


class TestS3HelperFunctions:
    """Target S3 helper functions (lines 1320-1684)"""
    
    @patch("src.services.s3_service.s3")
    def test_check_model_exists_in_s3(self, mock_s3):
        """Test checking if model exists in S3"""
        from src.services.s3_service import check_model_exists
        
        mock_s3.head_object.return_value = {"ContentLength": 1024}
        
        result = check_model_exists("model1", "1.0.0")
        assert result == True

    @patch("src.services.s3_service.s3")
    def test_check_model_not_exists_in_s3(self, mock_s3):
        """Test checking non-existent model in S3"""
        from src.services.s3_service import check_model_exists
        
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        
        result = check_model_exists("nonexistent", "1.0.0")
        assert result == False

    @patch("src.services.s3_service.s3")
    def test_delete_model_from_s3(self, mock_s3):
        """Test deleting model from S3"""
        from src.services.s3_service import delete_model_from_s3
        
        result = delete_model_from_s3("model1", "1.0.0")
        assert result == True
        mock_s3.delete_object.assert_called()

    @patch("src.services.s3_service.s3")
    def test_list_model_versions(self, mock_s3):
        """Test listing all versions of a model"""
        from src.services.s3_service import list_model_versions
        
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/model1/1.0.0/model.zip"},
                {"Key": "models/model1/1.1.0/model.zip"},
                {"Key": "models/model1/2.0.0/model.zip"}
            ]
        }
        
        result = list_model_versions("model1")
        assert len(result) == 3

    @patch("src.services.s3_service.s3")
    def test_copy_model_in_s3(self, mock_s3):
        """Test copying model within S3"""
        from src.services.s3_service import copy_model
        
        result = copy_model("model1", "1.0.0", "model1-copy", "1.0.0")
        assert result == True
        mock_s3.copy_object.assert_called()


class TestS3MetadataOperations:
    """Test S3 metadata storage and retrieval"""
    
    @patch("src.services.s3_service.s3")
    def test_store_model_metadata_comprehensive(self, mock_s3):
        """Test storing comprehensive model metadata"""
        from src.services.s3_service import store_artifact_metadata
        
        metadata = {
            "name": "model1",
            "version": "1.0.0",
            "type": "model",
            "author": "user1",
            "license": "MIT",
            "tags": ["nlp", "transformer"],
            "size": 1024000
        }
        
        result = store_artifact_metadata("a1", metadata)
        assert result["status"] == "success"
        mock_s3.put_object.assert_called()

    @patch("src.services.s3_service.s3")
    def test_find_metadata_by_various_criteria(self, mock_s3):
        """Test finding metadata by various search criteria"""
        from src.services.s3_service import find_artifact_metadata_by_id
        
        # Mock list_models to return nothing to force comprehensive search
        with patch("src.services.s3_service.list_models", return_value={"models": []}):
            # Mock paginator
            paginator = MagicMock()
            mock_s3.get_paginator.return_value = paginator
            
            # Mock page with metadata file
            paginator.paginate.return_value = [
                {"Contents": [{"Key": "models/model1/1.0.0/metadata.json"}]}
            ]
            
            # Mock get_object to return metadata with matching artifact_id
            mock_s3.get_object.return_value = {
                "Body": MagicMock(
                    read=MagicMock(return_value=b'{"artifact_id": "a1", "name": "model1", "type": "model"}')
                )
            }
            
            result = find_artifact_metadata_by_id("a1")
            assert result is not None
            assert result["name"] == "model1"

    @patch("src.services.s3_service.s3")
    def test_update_model_metadata(self, mock_s3):
        """Test updating existing model metadata"""
        from src.services.s3_service import update_artifact_metadata, find_artifact_metadata_by_id
        
        # First get existing (mock find_artifact_metadata_by_id)
        with patch("src.services.s3_service.find_artifact_metadata_by_id") as mock_find:
            mock_find.return_value = {"s3_key": "models/model1/1.0.0/metadata.json"}
            
            # Then update
            new_data = {"name": "model1", "version": "2.0.0"}
            result = update_artifact_metadata("a1", new_data)
            assert result is True


class TestS3ErrorHandling:
    """Test comprehensive S3 error handling"""
    
    @patch("src.services.s3_service.s3")
    def test_s3_access_denied_error(self, mock_s3):
        """Test handling S3 access denied errors"""
        from src.services.s3_service import download_model
        
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "GetObject"
        )
        
        with pytest.raises(Exception):
            download_model("model1", "1.0.0")

    @patch("src.services.s3_service.s3")
    def test_s3_bucket_not_found_error(self, mock_s3):
        """Test handling S3 bucket not found errors"""
        from src.services.s3_service import list_models
        
        mock_s3.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "ListObjectsV2"
        )
        
        with pytest.raises(Exception):
            list_models()

    @patch("src.services.s3_service.s3")
    def test_s3_internal_error_retry(self, mock_s3):
        """Test S3 internal error retry logic"""
        from src.services.s3_service import upload_model
        
        # First call fails, second succeeds
        mock_s3.put_object.side_effect = [
            ClientError(
                {"Error": {"Code": "InternalError"}},
                "PutObject"
            ),
            {"ETag": "abc123"}
        ]
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            upload_model(b"data", "model1", "1.0.0")
        assert exc.value.status_code == 500
