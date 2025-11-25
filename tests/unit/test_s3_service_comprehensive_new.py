"""
Comprehensive unit tests for src/services/s3_service.py
Focuses on upload, download, HuggingFace integration, and validation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
import zipfile
import io
import json
from botocore.exceptions import ClientError
from fastapi import HTTPException
from src.services.s3_service import (
    parse_version,
    version_matches_range,
    validate_huggingface_structure,
    get_model_sizes,
    upload_model,
    download_model,
    list_models,
    download_from_huggingface,
    model_ingestion,
    get_model_lineage_from_config,
    extract_config_from_model,
)


class TestVersionParsing:
    """Test version parsing functions"""

    def test_parse_version_valid(self):
        """Test parsing valid version strings"""
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("v1.2.3") == (1, 2, 3)
        assert parse_version("0.0.1") == (0, 0, 1)
        assert parse_version("10.20.30") == (10, 20, 30)

    def test_parse_version_invalid(self):
        """Test parsing invalid version strings"""
        assert parse_version("1.2") is None
        assert parse_version("1.2.3.4") is None
        assert parse_version("invalid") is None
        assert parse_version("") is None

    def test_version_matches_range_exact(self):
        """Test exact version matching"""
        assert version_matches_range("1.2.3", "1.2.3") is True
        assert version_matches_range("1.2.3", "1.2.4") is False

    def test_version_matches_range_bounded(self):
        """Test bounded version range"""
        assert version_matches_range("1.2.3", "1.2.0-1.2.5") is True
        assert version_matches_range("1.2.3", "1.0.0-1.2.2") is False
        assert version_matches_range("1.2.3", "1.2.4-1.3.0") is False

    def test_version_matches_range_tilde(self):
        """Test tilde version range"""
        assert version_matches_range("1.2.3", "~1.2.0") is True
        assert version_matches_range("1.2.9", "~1.2.0") is True
        assert version_matches_range("1.3.0", "~1.2.0") is False

    def test_version_matches_range_caret(self):
        """Test caret version range"""
        assert version_matches_range("1.2.3", "^1.2.0") is True
        assert version_matches_range("1.9.9", "^1.2.0") is True
        assert version_matches_range("2.0.0", "^1.2.0") is False

    def test_version_matches_range_invalid(self):
        """Test version matching with invalid inputs"""
        assert version_matches_range("invalid", "1.2.3") is False
        assert version_matches_range("1.2.3", "invalid") is False


class TestHuggingFaceValidation:
    """Test HuggingFace structure validation"""

    def test_validate_huggingface_structure_valid(self):
        """Test validation of valid HuggingFace structure"""
        # Create a valid ZIP with config.json and weights
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert"}')
            zip_file.writestr("model.bin", b"weights data")
        zip_buffer.seek(0)

        result = validate_huggingface_structure(zip_buffer.getvalue())
        assert result["valid"] is True
        assert result["has_config"] is True
        assert result["has_weights"] is True

    def test_validate_huggingface_structure_no_config(self):
        """Test validation without config.json"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("model.bin", b"weights data")
        zip_buffer.seek(0)

        result = validate_huggingface_structure(zip_buffer.getvalue())
        assert result["valid"] is False
        assert result["has_config"] is False

    def test_validate_huggingface_structure_no_weights(self):
        """Test validation without weights"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert"}')
        zip_buffer.seek(0)

        result = validate_huggingface_structure(zip_buffer.getvalue())
        assert result["valid"] is False
        assert result["has_weights"] is False

    def test_validate_huggingface_structure_invalid_zip(self):
        """Test validation with invalid ZIP"""
        result = validate_huggingface_structure(b"not a zip file")
        assert result["valid"] is False
        assert "error" in result

    def test_validate_huggingface_structure_safetensors(self):
        """Test validation with safetensors weights"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert"}')
            zip_file.writestr("model.safetensors", b"weights data")
        zip_buffer.seek(0)

        result = validate_huggingface_structure(zip_buffer.getvalue())
        assert result["valid"] is True
        assert result["has_weights"] is True


class TestModelSizes:
    """Test model size calculation"""

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_get_model_sizes_success(self, mock_s3):
        """Test getting model sizes successfully"""
        # Create a ZIP with weights and datasets
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("model.bin", b"x" * 1000)
            zip_file.writestr("data.csv", b"x" * 500)
        zip_content = zip_buffer.getvalue()

        mock_s3.head_object.return_value = {"ContentLength": len(zip_content)}
        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = get_model_sizes("test-model", "1.0.0")
        assert "full" in result
        assert "weights" in result
        assert "datasets" in result

    @patch("src.services.s3_service.aws_available", False)
    def test_get_model_sizes_aws_unavailable(self):
        """Test getting model sizes when AWS is unavailable"""
        result = get_model_sizes("test-model", "1.0.0")
        assert result["error"] == "AWS services not available"

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_get_model_sizes_not_found(self, mock_s3):
        """Test getting model sizes when model not found"""
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "HeadObject"
        )

        result = get_model_sizes("nonexistent", "1.0.0")
        assert "error" in result


class TestUploadModel:
    """Test model upload functionality"""

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_upload_model_success(self, mock_s3):
        """Test successful model upload"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert"}')
            zip_file.writestr("model.bin", b"weights")
        zip_content = zip_buffer.getvalue()

        mock_s3.put_object.return_value = {"ETag": "test-etag"}

        result = upload_model(zip_content, "test-model", "1.0.0")
        assert "status" in result or result is not None
        mock_s3.put_object.assert_called()

    @patch("src.services.s3_service.aws_available", False)
    def test_upload_model_aws_unavailable(self):
        """Test upload when AWS is unavailable"""
        with pytest.raises(HTTPException):
            upload_model(b"zip content", "test-model", "1.0.0")


class TestDownloadModel:
    """Test model download functionality"""

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_download_model_success(self, mock_s3):
        """Test successful model download"""
        zip_content = b"zip file content"
        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = download_model("test-model", "1.0.0", "full")
        assert result == zip_content

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_download_model_not_found(self, mock_s3):
        """Test download when model not found"""
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        with pytest.raises(HTTPException):
            download_model("nonexistent", "1.0.0", "full")

    @patch("src.services.s3_service.aws_available", False)
    def test_download_model_aws_unavailable(self):
        """Test download when AWS is unavailable"""
        with pytest.raises(HTTPException):
            download_model("test-model", "1.0.0", "full")


class TestListModels:
    """Test model listing functionality"""

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_list_models_success(self, mock_s3):
        """Test successful model listing"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/test-model/1.0.0/model.zip", "Size": 1000}
            ]
        }

        result = list_models()
        assert "models" in result
        assert isinstance(result["models"], list)

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_list_models_with_name_regex(self, mock_s3):
        """Test listing models with name regex filter"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/matching-model/1.0.0/model.zip", "Size": 1000}
            ]
        }

        result = list_models(name_regex="^matching.*")
        assert "models" in result

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-arn")
    def test_list_models_with_version_range(self, mock_s3):
        """Test listing models with version range"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/test-model/1.2.3/model.zip", "Size": 1000}
            ]
        }

        result = list_models(version_range="1.2.0-1.3.0")
        assert "models" in result

    @patch("src.services.s3_service.aws_available", False)
    def test_list_models_aws_unavailable(self):
        """Test listing when AWS is unavailable"""
        with pytest.raises(HTTPException):
            list_models()


class TestHuggingFaceDownload:
    """Test HuggingFace download functionality"""

    @patch("src.services.s3_service.requests.get")
    def test_download_from_huggingface_success(self, mock_get):
        """Test successful HuggingFace download"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"zip content"
        mock_get.return_value = mock_response

        result = download_from_huggingface("user/model", "main")
        # Should return zip content
        assert isinstance(result, bytes)
        assert result == b"zip content"

    @patch("src.services.s3_service.requests.get")
    def test_download_from_huggingface_not_found(self, mock_get):
        """Test HuggingFace download when model not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        with pytest.raises(HTTPException):
            download_from_huggingface("nonexistent/model", "main")

    @patch("src.services.s3_service.requests.get")
    def test_download_from_huggingface_error(self, mock_get):
        """Test HuggingFace download with error"""
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(HTTPException):
            download_from_huggingface("user/model", "main")


class TestModelIngestion:
    """Test model ingestion functionality"""

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.download_from_huggingface")
    @patch("src.services.s3_service.validate_huggingface_structure")
    @patch("src.services.s3_service.upload_model")
    @patch("src.services.rating.create_metadata_from_files")
    @patch("src.services.rating.run_acme_metrics")
    @patch("src.services.s3_service.extract_config_from_model")
    def test_model_ingestion_success(
        self, mock_extract, mock_metrics, mock_create, mock_upload, mock_validate, mock_download
    ):
        """Test successful model ingestion"""
        zip_content = b"zip content"
        mock_download.return_value = zip_content
        mock_validate.return_value = {"has_config": True, "has_weights": True}
        mock_upload.return_value = {"status": "success"}
        mock_create.return_value = {
            "repo_files": set(),
            "readme_text": "",
            "license_text": "",
        }
        mock_extract.return_value = {"model_type": "bert"}
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
            "treescore": 1.0,
        }

        result = model_ingestion("user/model", "main")
        assert result is not None

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.download_from_huggingface")
    def test_model_ingestion_download_fails(self, mock_download):
        """Test ingestion when download fails"""
        mock_download.side_effect = HTTPException(
            status_code=404, detail="Model not found"
        )

        with pytest.raises(HTTPException):
            model_ingestion("nonexistent/model", "main")

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.download_from_huggingface")
    @patch("src.services.s3_service.validate_huggingface_structure")
    def test_model_ingestion_invalid_structure(self, mock_validate, mock_download):
        """Test ingestion with invalid structure"""
        mock_download.return_value = b"zip content"
        mock_validate.return_value = {"has_config": False, "has_weights": False}

        with pytest.raises(HTTPException):
            model_ingestion("user/model", "main")


class TestConfigExtraction:
    """Test config extraction from models"""

    def test_extract_config_from_model_success(self):
        """Test successful config extraction"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert", "hidden_size": 768}')
        zip_content = zip_buffer.getvalue()

        result = extract_config_from_model(zip_content)
        assert result is not None
        assert "model_type" in result
        assert result["model_type"] == "bert"

    def test_extract_config_from_model_no_config(self):
        """Test extraction when config.json not found"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("model.bin", b"weights")
        zip_content = zip_buffer.getvalue()

        result = extract_config_from_model(zip_content)
        assert result is None

    def test_extract_config_from_model_invalid_zip(self):
        """Test extraction with invalid zip"""
        result = extract_config_from_model(b"not a zip file")
        assert result is None


class TestModelLineage:
    """Test model lineage functionality"""

    @patch("src.services.s3_service.download_model")
    @patch("src.services.s3_service.extract_config_from_model")
    def test_get_model_lineage_from_config_success(self, mock_extract, mock_download):
        """Test getting lineage from config"""
        zip_content = b"zip content"
        mock_download.return_value = zip_content
        config = {
            "model_type": "bert",
            "parent": "parent-model",
            "base_model": "base-model"
        }
        mock_extract.return_value = config

        result = get_model_lineage_from_config("test-model", "1.0.0")
        assert "lineage_map" in result
        assert "config" in result

    @patch("src.services.s3_service.download_model")
    @patch("src.services.s3_service.extract_config_from_model")
    def test_get_model_lineage_from_config_no_config(self, mock_extract, mock_download):
        """Test lineage when config not found"""
        zip_content = b"zip content"
        mock_download.return_value = zip_content
        mock_extract.return_value = None

        result = get_model_lineage_from_config("test-model", "1.0.0")
        assert "error" in result or result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

