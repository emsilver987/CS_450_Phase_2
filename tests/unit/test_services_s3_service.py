"""
Unit tests for src/services/s3_service.py
Focusing on core functions to improve coverage from 11% to ~40%
"""
import pytest
import zipfile
import io
import json
from unittest.mock import patch, MagicMock, Mock
from fastapi import HTTPException
from botocore.exceptions import ClientError

from src.services.s3_service import (
    parse_version,
    version_matches_range,
    validate_huggingface_structure,
    get_model_sizes,
    extract_model_component,
    get_presigned_upload_url,
    upload_model,
    download_model,
    search_model_card_content,
    list_models,
    extract_config_from_model,
    extract_github_url_from_text,
    parse_lineage_from_config,
    get_model_lineage_from_config,
    clear_model_card_cache,
    reset_registry,
    store_artifact_metadata,
    find_artifact_metadata_by_id,
    list_artifacts_from_s3,
    extract_github_url_from_zip,
)


class TestParseVersion:
    """Test parse_version function"""

    def test_parse_version_valid(self):
        """Test parsing valid version strings"""
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("0.0.1") == (0, 0, 1)
        assert parse_version("10.20.30") == (10, 20, 30)

    def test_parse_version_with_v_prefix(self):
        """Test parsing version with v prefix"""
        assert parse_version("v1.2.3") == (1, 2, 3)
        assert parse_version("v0.0.1") == (0, 0, 1)

    def test_parse_version_invalid(self):
        """Test parsing invalid version strings"""
        assert parse_version("1.2") is None
        assert parse_version("1.2.3.4") is None
        assert parse_version("invalid") is None
        assert parse_version("") is None
        assert parse_version("1.2.x") is None


class TestVersionMatchesRange:
    """Test version_matches_range function"""

    def test_exact_match(self):
        """Test exact version match"""
        assert version_matches_range("1.2.3", "1.2.3") is True
        assert version_matches_range("1.2.3", "2.0.0") is False

    def test_range_match(self):
        """Test version range matching"""
        assert version_matches_range("1.2.3", "1.2.0-1.3.0") is True
        assert version_matches_range("1.5.0", "1.2.0-1.3.0") is False
        assert version_matches_range("1.2.5", "1.2.0-1.3.0") is True

    def test_tilde_match(self):
        """Test tilde version matching (~)"""
        assert version_matches_range("1.2.3", "~1.2.0") is True
        assert version_matches_range("1.2.9", "~1.2.0") is True
        assert version_matches_range("1.3.0", "~1.2.0") is False
        assert version_matches_range("1.1.9", "~1.2.0") is False

    def test_caret_match(self):
        """Test caret version matching (^)"""
        assert version_matches_range("1.2.3", "^1.2.0") is True
        assert version_matches_range("1.9.9", "^1.2.0") is True
        assert version_matches_range("2.0.0", "^1.2.0") is False
        assert version_matches_range("0.9.9", "^1.2.0") is False

    def test_invalid_version(self):
        """Test with invalid version strings"""
        assert version_matches_range("invalid", "1.2.3") is False
        assert version_matches_range("1.2.3", "invalid") is False


class TestValidateHuggingfaceStructure:
    """Test validate_huggingface_structure function"""

    def test_valid_structure(self):
        """Test validation of valid HuggingFace structure"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert"}')
            zip_file.writestr("model.bin", b"weights")
        zip_content = zip_buffer.getvalue()

        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is True
        assert result["has_config"] is True
        assert result["has_weights"] is True

    def test_missing_config(self):
        """Test validation with missing config.json"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.bin", b"weights")
        zip_content = zip_buffer.getvalue()

        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is False
        assert result["has_config"] is False
        assert result["has_weights"] is True

    def test_missing_weights(self):
        """Test validation with missing weights"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("config.json", '{"model_type": "bert"}')
        zip_content = zip_buffer.getvalue()

        result = validate_huggingface_structure(zip_content)
        assert result["valid"] is False
        assert result["has_config"] is True
        assert result["has_weights"] is False

    def test_invalid_zip(self):
        """Test validation with invalid ZIP file"""
        invalid_zip = b"not a zip file"
        result = validate_huggingface_structure(invalid_zip)
        assert result["valid"] is False
        assert "error" in result


class TestExtractConfigFromModel:
    """Test extract_config_from_model function"""

    def test_extract_config_success(self):
        """Test successful config extraction"""
        config_data = {"model_type": "bert", "hidden_size": 768}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("config.json", json.dumps(config_data))
        zip_content = zip_buffer.getvalue()

        result = extract_config_from_model(zip_content)
        assert result == config_data

    def test_extract_config_nested_path(self):
        """Test extracting config from nested path"""
        config_data = {"model_type": "gpt2"}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model/config.json", json.dumps(config_data))
        zip_content = zip_buffer.getvalue()

        result = extract_config_from_model(zip_content)
        assert result == config_data

    def test_extract_config_not_found(self):
        """Test when config.json is not found"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("other_file.txt", "content")
        zip_content = zip_buffer.getvalue()

        result = extract_config_from_model(zip_content)
        assert result is None

    def test_extract_config_invalid_zip(self):
        """Test with invalid ZIP"""
        invalid_zip = b"not a zip"
        result = extract_config_from_model(invalid_zip)
        assert result is None


class TestExtractGithubUrlFromText:
    """Test extract_github_url_from_text function"""

    def test_extract_from_markdown_link(self):
        """Test extracting from markdown link"""
        text = "Check out [the repo](https://github.com/owner/repo)"
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_from_html_link(self):
        """Test extracting from HTML link"""
        text = '<a href="https://github.com/owner/repo">Link</a>'
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_from_plain_url(self):
        """Test extracting from plain URL"""
        text = "Repository: https://github.com/owner/repo"
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_from_owner_repo_format(self):
        """Test extracting from owner/repo format"""
        text = "The code is at github.com/owner/repo"
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_no_github_url(self):
        """Test when no GitHub URL is present"""
        text = "This is just some text without GitHub"
        result = extract_github_url_from_text(text)
        assert result is None

    def test_empty_text(self):
        """Test with empty text"""
        assert extract_github_url_from_text("") is None
        assert extract_github_url_from_text(None) is None


class TestParseLineageFromConfig:
    """Test parse_lineage_from_config function"""

    def test_parse_with_base_model(self):
        """Test parsing config with base_model_name_or_path"""
        config = {
            "base_model_name_or_path": "bert-base-uncased",
            "model_type": "bert",
            "architectures": ["BertModel"],
        }
        result = parse_lineage_from_config(config, "my-model")
        assert result["base_model"] == "bert-base-uncased"
        assert result["model_type"] == "bert"
        assert result["architectures"] == ["BertModel"]

    def test_parse_with_name_or_path(self):
        """Test parsing config with _name_or_path"""
        config = {"_name_or_path": "gpt2", "model_type": "gpt2"}
        result = parse_lineage_from_config(config, "my-model")
        assert result["base_model"] == "gpt2"

    def test_parse_without_base_model(self):
        """Test parsing config without base model"""
        config = {"model_type": "custom", "vocab_size": 1000}
        result = parse_lineage_from_config(config, "my-model")
        assert result["base_model"] is None
        assert result["model_type"] == "custom"
        assert result["vocab_size"] == 1000


class TestS3ServiceWithMocks:
    """Test S3 service functions with mocked AWS"""

    @patch("src.services.s3_service.aws_available", False)
    def test_get_model_sizes_aws_unavailable(self):
        """Test get_model_sizes when AWS is unavailable"""
        result = get_model_sizes("test-model", "1.0.0")
        assert result["error"] == "AWS services not available"
        assert result["full"] == 0

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_get_model_sizes_success(self, mock_s3):
        """Test successful get_model_sizes"""
        # Create a mock ZIP with weights and datasets
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.bin", b"weights" * 100)
            zip_file.writestr("data.csv", b"dataset" * 50)
        zip_content = zip_buffer.getvalue()

        mock_s3.head_object.return_value = {"ContentLength": len(zip_content)}
        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = get_model_sizes("test-model", "1.0.0")
        assert result["full"] == len(zip_content)
        assert "weights" in result
        assert "datasets" in result

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_get_model_sizes_not_found(self, mock_s3):
        """Test get_model_sizes when model not found"""
        error_response = {"Error": {"Code": "404"}}
        mock_s3.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )

        result = get_model_sizes("test-model", "1.0.0")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_upload_model_success(self, mock_s3):
        """Test successful upload_model"""
        file_content = b"test zip content"
        mock_s3.put_object.return_value = {}

        result = upload_model(file_content, "test-model", "1.0.0")
        assert result["message"] == "Upload successful"
        mock_s3.put_object.assert_called_once()

    @patch("src.services.s3_service.aws_available", False)
    def test_upload_model_aws_unavailable(self):
        """Test upload_model when AWS is unavailable"""
        with pytest.raises(HTTPException) as exc:
            upload_model(b"content", "test-model", "1.0.0")
        assert exc.value.status_code == 503

    @patch("src.services.s3_service.aws_available", True)
    def test_upload_model_empty_content(self):
        """Test upload_model with empty content"""
        with pytest.raises(HTTPException) as exc:
            upload_model(b"", "test-model", "1.0.0")
        assert exc.value.status_code == 400

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_upload_model_access_denied(self, mock_s3):
        """Test upload_model with access denied error"""
        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_s3.put_object.side_effect = ClientError(
            error_response, "PutObject"
        )

        with pytest.raises(HTTPException) as exc:
            upload_model(b"content", "test-model", "1.0.0")
        assert exc.value.status_code == 403

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_download_model_success(self, mock_s3):
        """Test successful download_model"""
        zip_content = b"test zip content"
        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = download_model("test-model", "1.0.0")
        assert result == zip_content

    @patch("src.services.s3_service.aws_available", False)
    def test_download_model_aws_unavailable(self):
        """Test download_model when AWS is unavailable"""
        with pytest.raises(HTTPException) as exc:
            download_model("test-model", "1.0.0")
        assert exc.value.status_code == 503

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_download_model_component_weights(self, mock_s3):
        """Test download_model with weights component"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.bin", b"weights")
            zip_file.writestr("data.csv", b"dataset")
        zip_content = zip_buffer.getvalue()

        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = download_model("test-model", "1.0.0", "weights")
        # Should return a ZIP with only weight files
        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_get_presigned_upload_url_success(self, mock_s3):
        """Test successful get_presigned_upload_url"""
        mock_s3.generate_presigned_url.return_value = (
            "https://presigned-url.example.com"
        )

        result = get_presigned_upload_url("test-model", "1.0.0")
        assert "upload_url" in result
        assert result["model_id"] == "test-model"
        assert result["version"] == "1.0.0"

    @patch("src.services.s3_service.aws_available", False)
    def test_get_presigned_upload_url_aws_unavailable(self):
        """Test get_presigned_upload_url when AWS is unavailable"""
        with pytest.raises(HTTPException) as exc:
            get_presigned_upload_url("test-model", "1.0.0")
        assert exc.value.status_code == 503

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_list_models_success(self, mock_s3):
        """Test successful list_models"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/test-model/1.0.0/model.zip"},
                {"Key": "models/other-model/2.0.0/model.zip"},
            ]
        }

        result = list_models()
        assert "models" in result
        assert len(result["models"]) == 2

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_list_models_with_name_regex(self, mock_s3):
        """Test list_models with name regex filter"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/test-model/1.0.0/model.zip"},
                {"Key": "models/other-model/2.0.0/model.zip"},
            ]
        }

        result = list_models(name_regex="^test.*")
        assert len(result["models"]) == 1
        assert result["models"][0]["name"] == "test-model"

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_list_models_invalid_regex(self, mock_s3):
        """Test list_models with invalid regex"""
        # Need to provide a response with Contents so the regex is actually checked
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/test-model/1.0.0/model.zip"},
            ]
        }
        with pytest.raises(HTTPException) as exc:
            list_models(name_regex="[invalid")
        assert exc.value.status_code == 400

    @patch("src.services.s3_service.aws_available", False)
    def test_list_models_aws_unavailable(self):
        """Test list_models when AWS is unavailable"""
        with pytest.raises(HTTPException) as exc:
            list_models()
        assert exc.value.status_code == 503

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_reset_registry_success(self, mock_s3):
        """Test successful reset_registry"""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/test-model/1.0.0/model.zip"},
            ]
        }
        mock_s3.delete_object.return_value = {}

        result = reset_registry()
        assert result["message"] == "Reset done successfully"
        mock_s3.delete_object.assert_called_once()

    @patch("src.services.s3_service.aws_available", False)
    def test_reset_registry_aws_unavailable(self):
        """Test reset_registry when AWS is unavailable"""
        with pytest.raises(HTTPException) as exc:
            reset_registry()
        assert exc.value.status_code == 503

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_get_model_lineage_from_config_success(self, mock_s3):
        """Test successful get_model_lineage_from_config"""
        config_data = {
            "base_model_name_or_path": "bert-base-uncased",
            "model_type": "bert",
        }
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("config.json", json.dumps(config_data))
        zip_content = zip_buffer.getvalue()

        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = get_model_lineage_from_config("test-model", "1.0.0")
        assert result["model_id"] == "test-model"
        assert "lineage_metadata" in result
        assert result["lineage_metadata"]["base_model"] == "bert-base-uncased"

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_get_model_lineage_no_config(self, mock_s3):
        """Test get_model_lineage_from_config when config not found"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("other_file.txt", "content")
        zip_content = zip_buffer.getvalue()

        mock_s3.get_object.return_value = {"Body": io.BytesIO(zip_content)}

        result = get_model_lineage_from_config("test-model", "1.0.0")
        assert "error" in result
        assert "No config.json" in result["error"]

    def test_extract_model_component_weights(self):
        """Test extract_model_component with weights"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.bin", b"weights")
            zip_file.writestr("data.csv", b"dataset")
        zip_content = zip_buffer.getvalue()

        result = extract_model_component(zip_content, "weights")
        assert isinstance(result, bytes)
        # Verify it's a valid ZIP
        with zipfile.ZipFile(io.BytesIO(result), "r") as zip_file:
            assert "model.bin" in zip_file.namelist()
            assert "data.csv" not in zip_file.namelist()

    def test_extract_model_component_datasets(self):
        """Test extract_model_component with datasets"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.bin", b"weights")
            zip_file.writestr("data.txt", b"dataset")
            zip_file.writestr("data.json", b'{"key": "value"}')
        zip_content = zip_buffer.getvalue()

        result = extract_model_component(zip_content, "datasets")
        assert isinstance(result, bytes)
        with zipfile.ZipFile(io.BytesIO(result), "r") as zip_file:
            assert "data.txt" in zip_file.namelist()
            assert "data.json" in zip_file.namelist()

    def test_extract_model_component_full(self):
        """Test extract_model_component with full"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.bin", b"weights")
            zip_file.writestr("data.txt", b"dataset")
        zip_content = zip_buffer.getvalue()

        result = extract_model_component(zip_content, "full")
        assert result == zip_content

    def test_extract_model_component_no_files(self):
        """Test extract_model_component when no matching files"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("other.txt", b"content")
        zip_content = zip_buffer.getvalue()

        with pytest.raises(ValueError):
            extract_model_component(zip_content, "weights")

    def test_clear_model_card_cache(self):
        """Test clear_model_card_cache"""
        # Should not raise any exceptions
        clear_model_card_cache()

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_store_artifact_metadata_success(self, mock_s3):
        """Test successful store_artifact_metadata"""
        mock_s3.put_object.return_value = {}

        result = store_artifact_metadata(
            "artifact-123", "test-artifact", "model", "1.0.0", "http://example.com"
        )
        assert result["status"] == "success"
        assert "s3_key" in result

    @patch("src.services.s3_service.aws_available", False)
    def test_store_artifact_metadata_aws_unavailable(self):
        """Test store_artifact_metadata when AWS is unavailable"""
        result = store_artifact_metadata(
            "artifact-123", "test-artifact", "model", "1.0.0", "http://example.com"
        )
        assert result["status"] == "skipped"

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_list_artifacts_from_s3_models(self, mock_s3):
        """Test list_artifacts_from_s3 for models"""
        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "models/test-model/1.0.0/model.zip"},
                ]
            }
        ]

        result = list_artifacts_from_s3("model")
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["name"] == "test-model"

    @patch("src.services.s3_service.aws_available", False)
    def test_list_artifacts_from_s3_aws_unavailable(self):
        """Test list_artifacts_from_s3 when AWS is unavailable"""
        result = list_artifacts_from_s3("model")
        assert result["artifacts"] == []

    @patch("src.services.s3_service.aws_available", True)
    @patch("src.services.s3_service.s3")
    @patch("src.services.s3_service.ap_arn", "test-bucket")
    def test_find_artifact_metadata_by_id_not_found(self, mock_s3):
        """Test find_artifact_metadata_by_id when not found"""
        mock_s3.list_objects_v2.return_value = {"models": []}
        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": []}]

        result = find_artifact_metadata_by_id("nonexistent-id")
        assert result is None

    @patch("src.services.s3_service.aws_available", False)
    def test_find_artifact_metadata_by_id_aws_unavailable(self):
        """Test find_artifact_metadata_by_id when AWS is unavailable"""
        result = find_artifact_metadata_by_id("test-id")
        assert result is None

    def test_extract_github_url_from_zip_success(self):
        """Test extract_github_url_from_zip with GitHub URL in README"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr(
                "README.md", "Check out https://github.com/owner/repo"
            )
        zip_content = zip_buffer.getvalue()

        result = extract_github_url_from_zip(zip_content)
        assert result == "https://github.com/owner/repo"

    def test_extract_github_url_from_zip_no_url(self):
        """Test extract_github_url_from_zip when no URL found"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("README.md", "No GitHub URL here")
        zip_content = zip_buffer.getvalue()

        result = extract_github_url_from_zip(zip_content)
        assert result is None

    def test_extract_github_url_from_zip_empty(self):
        """Test extract_github_url_from_zip with empty content"""
        assert extract_github_url_from_zip(None) is None
        assert extract_github_url_from_zip(b"") is None

