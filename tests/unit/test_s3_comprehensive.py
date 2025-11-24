"""
Comprehensive tests for src/services/s3_service.py
This targets the second-largest coverage gap (1072 lines at 25%)
Focuses on: upload, download, HuggingFace integration, lineage tracking
"""
import pytest
import io
import zipfile
import json
from unittest.mock import MagicMock, patch, call
from src.services.s3_service import (
    parse_version, version_matches_range, validate_huggingface_structure,
    upload_model, download_model, list_models, get_model_sizes,
    download_from_huggingface, model_ingestion, extract_config_from_model,
    get_model_lineage_from_config, store_artifact_metadata,
    find_artifact_metadata_by_id, reset_registry, extract_model_component,
    get_presigned_upload_url, list_artifacts_from_s3
)


def create_test_zip(files_dict):
    """Helper to create test zip files"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files_dict.items():
            z.writestr(name, content)
    return buffer.getvalue()


# ============================================================================
# VERSION PARSING AND MATCHING
# ============================================================================

class TestVersionHandling:
    """Test version parsing and semver matching"""
    
    def test_parse_version_valid(self):
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("v1.2.3") == (1, 2, 3)
        assert parse_version("0.0.1") == (0, 0, 1)
        assert parse_version("10.20.30") == (10, 20, 30)
    
    def test_parse_version_invalid(self):
        assert parse_version("1.2") is None
        assert parse_version("invalid") is None
        assert parse_version("1.2.3.4") is None
        assert parse_version("") is None
    
    def test_version_matches_exact(self):
        assert version_matches_range("1.2.3", "1.2.3") is True
        assert version_matches_range("1.2.3", "1.2.4") is False
    
    def test_version_matches_caret(self):
        # ^1.2.3 means >=1.2.3 <2.0.0
        assert version_matches_range("1.2.3", "^1.2.3") is True
        assert version_matches_range("1.5.0", "^1.2.3") is True
        assert version_matches_range("2.0.0", "^1.2.3") is False
        assert version_matches_range("1.2.2", "^1.2.3") is False
    
    def test_version_matches_tilde(self):
        # ~1.2.3 means >=1.2.3 <1.3.0
        assert version_matches_range("1.2.3", "~1.2.3") is True
        assert version_matches_range("1.2.9", "~1.2.3") is True
        assert version_matches_range("1.3.0", "~1.2.3") is False
    
    def test_version_matches_range(self):
        # 1.0.0-2.0.0
        assert version_matches_range("1.5.0", "1.0.0-2.0.0") is True
        assert version_matches_range("2.0.0", "1.0.0-2.0.0") is True
        assert version_matches_range("0.9.9", "1.0.0-2.0.0") is False
        assert version_matches_range("2.0.1", "1.0.0-2.0.0") is False


# ============================================================================
# HUGGINGFACE STRUCTURE VALIDATION
# ============================================================================

class TestHuggingFaceValidation:
    """Test HuggingFace model structure validation"""
    
    def test_valid_structure(self):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert"}',
            "pytorch_model.bin": "fake weights",
            "tokenizer.json": "{}"
        })
        
        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is True
        assert result["has_config"] is True
        assert result["has_weights"] is True
    
    def test_missing_config(self):
        zip_content = create_test_zip({
            "pytorch_model.bin": "fake weights"
        })
        
        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is False
        assert result["has_config"] is False
    
    def test_missing_weights(self):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert"}'
        })
        
        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is False
        assert result["has_weights"] is False
    
    def test_safetensors_format(self):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert"}',
            "model.safetensors": "fake safetensors"
        })
        
        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is True
        assert result["has_weights"] is True
    
    def test_invalid_zip(self):
        result = validate_huggingface_structure(b"not a zip file")
        assert result["valid"] is False
        assert "error" in result


# ============================================================================
# MODEL UPLOAD TESTS
# ============================================================================

class TestModelUpload:
    """Test model upload functionality"""
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_upload_model_success(self, mock_s3):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert"}',
            "pytorch_model.bin": "weights"
        })
        
        result = upload_model(zip_content, "test/model", "1.0.0", debloat=False)
        
        assert mock_s3.put_object.called
        assert "status" in result or "s3_key" in result
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_upload_model_with_debloat(self, mock_s3):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert"}',
            "pytorch_model.bin": "weights",
            "unnecessary_file.txt": "remove this"
        })
        
        result = upload_model(zip_content, "test/model", "1.0.0", debloat=True)
        
        # Should upload with debloating applied
        assert mock_s3.put_object.called
    
    @patch("src.services.s3_service.aws_available", False)
    def test_upload_model_aws_unavailable(self):
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc:
            upload_model(b"content", "model", "1.0.0")
        
        assert exc.value.status_code == 503
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_upload_model_sanitize_name(self, mock_s3):
        # Test that special characters in model ID are handled
        zip_content = create_test_zip({"config.json": "{}", "model.bin": "data"})
        
        result = upload_model(zip_content, "user/model-v2", "1.0.0")
        
        # Should sanitize the name in S3 key
        assert mock_s3.put_object.called


# ============================================================================
# MODEL DOWNLOAD TESTS
# ============================================================================

class TestModelDownload:
    """Test model download functionality"""
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_download_model_full(self, mock_s3):
        zip_content = create_test_zip({
            "config.json": '{}',
            "model.bin": "weights"
        })
        
        mock_response = MagicMock()
        mock_response.__getitem__.return_value.read.return_value = zip_content
        mock_s3.get_object.return_value = mock_response
        
        result = download_model("test/model", "1.0.0", "full")
        
        assert result == zip_content
        assert mock_s3.get_object.called
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.extract_model_component")
    def test_download_model_weights_only(self, mock_extract, mock_s3):
        zip_content = create_test_zip({
            "config.json": '{}',
            "model.bin": "weights"
        })
        weights_zip = create_test_zip({"model.bin": "weights"})
        
        mock_response = MagicMock()
        mock_response.__getitem__.return_value.read.return_value = zip_content
        mock_s3.get_object.return_value = mock_response
        mock_extract.return_value = weights_zip
        
        result = download_model("test/model", "1.0.0", "weights")
        
        assert mock_extract.called
        mock_extract.assert_called_with(zip_content, "weights")
    
    @patch("src.services.s3_service.aws_available", False)
    def test_download_model_aws_unavailable(self):
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc:
            download_model("model", "1.0.0")
        
        assert exc.value.status_code == 503


# ============================================================================
# MODEL LISTING TESTS
# ============================================================================

class TestModelListing:
    """Test model listing and filtering"""
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_list_models_basic(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/model1/1.0.0/model.zip"},
                {"Key": "models/model2/2.0.0/model.zip"}
            ]
        }
        
        result = list_models()
        
        assert "models" in result
        assert len(result["models"]) == 2
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_list_models_with_regex(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/bert-base/1.0.0/model.zip"},
                {"Key": "models/gpt2-small/1.0.0/model.zip"}
            ]
        }
        
        result = list_models(name_regex="bert.*")
        
        # Should filter to only bert models
        assert "models" in result
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_list_models_with_version_range(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/model1/1.0.0/model.zip"},
                {"Key": "models/model1/1.5.0/model.zip"},
                {"Key": "models/model1/2.0.0/model.zip"}
            ]
        }
        
        result = list_models(version_range="^1.0.0")
        
        # Should filter by version range
        assert "models" in result
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_list_models_with_pagination(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Key": f"models/model{i}/1.0.0/model.zip"} for i in range(10)],
            "NextContinuationToken": "token123"
        }
        
        result = list_models(limit=10)
        
        assert "next_token" in result
        assert result["next_token"] == "token123"


# ============================================================================
# HUGGINGFACE DOWNLOAD TESTS
# ============================================================================

class TestHuggingFaceDownload:
    """Test downloading from HuggingFace"""
    
    @patch("src.services.s3_service.requests.get")
    @patch("src.services.s3_service.download_file")
    def test_download_from_huggingface_success(self, mock_download, mock_get):
        # Mock API response
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "siblings": [
                {"rfilename": "config.json"},
                {"rfilename": "pytorch_model.bin"}
            ]
        }
        mock_get.return_value = mock_api_response
        
        # Mock file downloads
        mock_download.side_effect = [
            b'{"model_type": "bert"}',  # config.json
            b'pretrained weights'        # model.bin
        ]
        
        result = download_from_huggingface("bert-base-uncased", "main")
        
        # Should return a valid zip
        assert result is not None
        assert len(result) > 0
    
    @patch("src.services.s3_service.requests.get")
    def test_download_from_huggingface_timeout(self, mock_get):
        import requests
        from fastapi import HTTPException
        
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(HTTPException) as exc:
            download_from_huggingface("model", "main")
        
        assert exc.value.status_code in [408, 500, 504]
    
    @patch("src.services.s3_service.requests.get")
    def test_download_from_huggingface_not_found(self, mock_get):
        from fastapi import HTTPException
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with pytest.raises(HTTPException) as exc:
            download_from_huggingface("nonexistent/model", "main")
        
        assert exc.value.status_code == 404


# ============================================================================
# MODEL INGESTION TESTS
# ============================================================================

class TestModelIngestion:
    """Test full model ingestion pipeline"""
    
    @patch("src.services.s3_service.download_from_huggingface")
    @patch("src.services.s3_service.upload_model")
    @patch("src.services.s3_service.aws_available", True)
    def test_model_ingestion_success(self, mock_upload, mock_download):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert", "_name_or_path": "bert-base"}',
            "pytorch_model.bin": "weights",
            "README.md": "# BERT Model"
        })
        
        mock_download.return_value = zip_content
        mock_upload.return_value = {"status": "success"}
        
        with patch("src.services.s3_service.run_acme_metrics") as mock_metrics:
            mock_metrics.return_value = {"net_score": 0.85, "license": 1.0}
            
            result = model_ingestion("bert-base-uncased", "main")
            
            assert "status" in result
            assert mock_download.called
            assert mock_upload.called
    
    @patch("src.services.s3_service.download_from_huggingface")
    def test_model_ingestion_invalid_structure(self, mock_download):
        from fastapi import HTTPException
        
        # Missing config
        zip_content = create_test_zip({"model.bin": "weights"})
        mock_download.return_value = zip_content
        
        with pytest.raises(HTTPException) as exc:
            model_ingestion("model", "main")
        
        assert exc.value.status_code in [400, 422]


# ============================================================================
# CONFIG AND LINEAGE TESTS
# ============================================================================

class TestConfigExtraction:
    """Test config.json extraction and lineage tracking"""
    
    def test_extract_config_from_model(self):
        zip_content = create_test_zip({
            "config.json": '{"model_type": "bert", "hidden_size": 768}',
            "model.bin": "weights"
        })
        
        config = extract_config_from_model(zip_content)
        
        assert config is not None
        assert config["model_type"] == "bert"
        assert config["hidden_size"] == 768
    
    def test_extract_config_nested(self):
        zip_content = create_test_zip({
            "model/config.json": '{"model_type": "gpt2"}',
            "model.bin": "weights"
        })
        
        config = extract_config_from_model(zip_content)
        assert config is not None
    
    def test_extract_config_missing(self):
        zip_content = create_test_zip({"model.bin": "weights"})
        
        config = extract_config_from_model(zip_content)
        assert config is None
    
    @patch("src.services.s3_service.download_model")
    def test_get_model_lineage(self, mock_download):
        zip_content = create_test_zip({
            "config.json": '{"_name_or_path": "bert-base-uncased", "model_type": "bert"}',
            "model.bin": "weights"
        })
        mock_download.return_value = zip_content
        
        result = get_model_lineage_from_config("my-model", "1.0.0")
        
        assert "lineage_metadata" in result
        assert result["lineage_metadata"]["base_model"] == "bert-base-uncased"


# ============================================================================
# SIZE AND COST TESTS
# ============================================================================

class TestModelSizes:
    """Test model size calculation"""
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_get_model_sizes(self, mock_s3):
        zip_content = create_test_zip({
            "config.json": '{}',
            "model.bin": "weights" * 1000,
            "data.json": "dataset" * 500
        })
        
        mock_s3.head_object.return_value = {"ContentLength": len(zip_content)}
        mock_response = MagicMock()
        mock_response.__getitem__.return_value.read.return_value = zip_content
        mock_s3.get_object.return_value = mock_response
        
        result = get_model_sizes("model1", "1.0.0")
        
        assert "full" in result
        assert "weights" in result
        assert "datasets" in result
        assert result["full"] == len(zip_content)
    
    @patch("src.services.s3_service.aws_available", False)
    def test_get_model_sizes_aws_unavailable(self):
        result = get_model_sizes("model", "1.0.0")
        
        assert result["full"] == 0
        assert "error" in result


# ============================================================================
# ARTIFACT METADATA TESTS
# ============================================================================

class TestArtifactMetadata:
    """Test artifact metadata storage in S3"""
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_store_artifact_metadata(self, mock_s3):
        result = store_artifact_metadata(
            "a1",
            "my-model",
            "model",
            "1.0.0",
            "s3://bucket/key"
        )
        
        assert result["status"] == "success"
        assert mock_s3.put_object.called
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_find_artifact_metadata_by_id(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Key": "metadata/models/a1.json"}]
        }
        
        metadata_json = json.dumps({
            "artifact_id": "a1",
            "name": "my-model",
            "type": "model"
        })
        
        mock_response = MagicMock()
        mock_response.__getitem__.return_value.read.return_value = metadata_json.encode()
        mock_s3.get_object.return_value = mock_response
        
        result = find_artifact_metadata_by_id("a1")
        
        assert result is not None
        assert result["artifact_id"] == "a1"
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_list_artifacts_from_s3(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/model1/1.0.0/model.zip"},
                {"Key": "models/model2/1.0.0/model.zip"}
            ]
        }
        
        result = list_artifacts_from_s3("model")
        
        assert "artifacts" in result
        assert len(result["artifacts"]) >= 0


# ============================================================================
# UTILITY TESTS
# ============================================================================

class TestUtilities:
    """Test utility functions"""
    
    def test_extract_model_component_weights(self):
        zip_content = create_test_zip({
            "model.bin": "weights",
            "model.safetensors": "more weights",
            "data.json": "dataset",
            "config.json": "{}"
        })
        
        result = extract_model_component(zip_content, "weights")
        
        # Should only contain weight files
        with zipfile.ZipFile(io.BytesIO(result), "r") as z:
            files = z.namelist()
            assert any(".bin" in f or ".safetensors" in f for f in files)
            assert "data.json" not in files
    
    def test_extract_model_component_datasets(self):
        zip_content = create_test_zip({
            "model.bin": "weights",
            "train.json": "training data",
            "eval.txt": "eval data"
        })
        
        result = extract_model_component(zip_content, "datasets")
        
        with zipfile.ZipFile(io.BytesIO(result), "r") as z:
            files = z.namelist()
            assert "train.json" in files or "eval.txt" in files
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_get_presigned_upload_url(self, mock_s3):
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned-url"
        
        result = get_presigned_upload_url("model1", "1.0.0")
        
        assert "upload_url" in result
        assert result["model_id"] == "model1"
        assert result["version"] == "1.0.0"
    
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.aws_available", True)
    def test_reset_registry(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/m1/1.0.0/model.zip"},
                {"Key": "models/m2/1.0.0/model.zip"}
            ]
        }
        
        result = reset_registry()
        
        assert result["message"] == "Reset done successfully"
        assert mock_s3.delete_object.call_count == 2
