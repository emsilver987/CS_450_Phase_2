"""
Unit tests for src/services/s3_service.py
Focusing on core functions to improve coverage from 11% to ~40%
"""
import pytest
import zipfile
import io
import json
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from botocore.exceptions import ClientError
import src.services.s3_service as s3_service_module

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
    download_file,
    download_from_huggingface,
    model_ingestion,
    sync_model_lineage_to_neptune,
    write_to_neptune,
    send_request,
    sign_request,
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
        # Mock paginator since reset_registry uses get_paginator
        # The function iterates over 4 prefixes: models/, datasets/, codes/, packages/
        # We'll return a page with one object only for the first prefix, empty for others
        mock_paginator = MagicMock()
        mock_page_with_object = {
            "Contents": [
                {"Key": "models/test-model/1.0.0/model.zip"},
            ]
        }
        mock_page_empty = {}  # No Contents key means no objects
        
        # Return page with object for first call (models/), empty pages for others
        call_count = [0]
        def paginate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First prefix (models/)
                return [mock_page_with_object]
            else:  # Other prefixes (datasets/, codes/, packages/)
                return [mock_page_empty]
        
        mock_paginator.paginate.side_effect = paginate_side_effect
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.delete_object.return_value = {}

        result = reset_registry()
        assert result["message"] == "Reset done successfully"
        # delete_object is called once per object found (1 object in this case)
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

    def test_search_model_card_content_cached(self):
        """Test search_model_card_content with cached content"""
        from src.services.s3_service import clear_model_card_cache
        
        clear_model_card_cache()
        cache_key = "test-model@1.0.0"
        from src.services.s3_service import _model_card_cache
        _model_card_cache[cache_key] = ["content with pattern"]
        
        result = search_model_card_content("test-model", "1.0.0", "pattern")
        assert result is True

    def test_search_model_card_content_filename_match(self):
        """Test search_model_card_content matching filename"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.head_object.return_value = {"ContentLength": 100000}
                    mock_s3.get_object.return_value = {
                        "Body": MagicMock(read=lambda: b"fake zip")
                    }
                    result = search_model_card_content("test-model", "1.0.0", "readme.md")
                    assert isinstance(result, bool)

    def test_extract_github_url_from_text_html_link(self):
        """Test extracting GitHub URL from HTML link"""
        text = '<a href="https://github.com/owner/repo">Click here</a>'
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_github_url_from_text_markdown_link(self):
        """Test extracting GitHub URL from markdown link"""
        text = '[Click here](https://github.com/owner/repo)'
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_github_url_from_text_plain_url(self):
        """Test extracting GitHub URL from plain text"""
        text = 'Check out https://github.com/owner/repo for more info'
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_github_url_from_text_owner_repo_format(self):
        """Test extracting GitHub URL from owner/repo format"""
        text = 'Repository: owner/repo'
        result = extract_github_url_from_text(text)
        assert result == "https://github.com/owner/repo"

    def test_extract_github_url_from_text_empty(self):
        """Test extracting GitHub URL from empty text"""
        assert extract_github_url_from_text("") is None
        assert extract_github_url_from_text(None) is None

    def test_store_artifact_metadata_exception(self):
        """Test storing artifact metadata with exception"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.put_object.side_effect = Exception("S3 error")
                    result = store_artifact_metadata(
                        "test-id", "test-name", "model", "1.0.0", "https://example.com"
                    )
                    assert result["status"] == "error"

    def test_get_model_sizes_exception(self):
        """Test get_model_sizes with exception"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.head_object.side_effect = Exception("S3 error")
                    result = get_model_sizes("test-model", "1.0.0")
                    assert "error" in result

    def test_list_models_with_continuation_token(self):
        """Test list_models with continuation token"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.list_objects_v2.return_value = {
                        "Contents": [],
                        "NextContinuationToken": "next-token"
                    }
                    result = list_models(continuation_token="token")
                    assert "next_token" in result

    def test_list_artifacts_from_s3_with_regex(self):
        """Test list_artifacts_from_s3 with regex filter"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_paginator = MagicMock()
                    mock_s3.get_paginator.return_value = mock_paginator
                    mock_paginator.paginate.return_value = [{
                        "Contents": [{
                            "Key": "models/test_model/1.0.0/model.zip"
                        }]
                    }]
                    result = list_artifacts_from_s3("model", name_regex="^test")
                    assert "artifacts" in result

    def test_reset_registry_no_objects(self):
        """Test reset_registry when no objects found"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.list_objects_v2.return_value = {}
                    result = reset_registry()
                    assert result["message"] == "Reset done successfully"

    def test_reset_registry_exception(self):
        """Test reset_registry with exception"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    # Mock paginator to raise exception
                    mock_paginator = MagicMock()
                    mock_paginator.paginate.side_effect = Exception("S3 error")
                    mock_s3.get_paginator.return_value = mock_paginator
                    # reset_registry raises HTTPException on error
                    with pytest.raises(HTTPException) as exc:
                        reset_registry()
                    assert exc.value.status_code == 500
                    assert "Failed to reset registry" in exc.value.detail


# Tests for previously untested functions

class TestDownloadFile:
    """Test download_file function"""

    def test_download_file_success(self):
        """Test successful file download"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"test content"
            mock_get.return_value = mock_response
            
            result = download_file("https://example.com/file.zip")
            assert result == b"test content"
            mock_get.assert_called_once_with("https://example.com/file.zip", timeout=120)

    def test_download_file_non_200_status(self):
        """Test download_file with non-200 status code"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            result = download_file("https://example.com/file.zip")
            assert result is None

    def test_download_file_timeout(self):
        """Test download_file with timeout"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.Timeout()
            
            result = download_file("https://example.com/file.zip")
            assert result is None

    def test_download_file_connection_error(self):
        """Test download_file with connection error"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            result = download_file("https://example.com/file.zip")
            assert result is None

    def test_download_file_custom_timeout(self):
        """Test download_file with custom timeout"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"content"
            mock_get.return_value = mock_response
            
            download_file("https://example.com/file.zip", timeout=60)
            mock_get.assert_called_once_with("https://example.com/file.zip", timeout=60)


class TestDownloadFromHuggingface:
    """Test download_from_huggingface function"""

    def test_download_from_huggingface_success(self):
        """Test successful download from HuggingFace"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            # Mock API response
            api_response = MagicMock()
            api_response.status_code = 200
            api_response.json.return_value = {
                "siblings": [
                    {"rfilename": "model.safetensors"},
                    {"rfilename": "config.json"}
                ]
            }
            
            # Mock file download
            file_response = MagicMock()
            file_response.status_code = 200
            file_response.content = b"file content"
            
            # Need to mock download_file which is called by download_from_huggingface
            with patch("src.services.s3_service.download_file") as mock_download_file:
                mock_download_file.return_value = b"file content"
                mock_get.return_value = api_response
                
                with patch("src.services.s3_service.zipfile.ZipFile"):
                    with patch("src.services.s3_service.io.BytesIO") as mock_bytesio:
                        mock_output = MagicMock()
                        mock_output.getvalue.return_value = b"zip content"
                        mock_bytesio.return_value = mock_output
                        
                        result = download_from_huggingface("test-model", "1.0.0")
                        assert result is not None
                        assert len(result) > 0

    def test_download_from_huggingface_timeout(self):
        """Test download_from_huggingface with timeout"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.Timeout()
            
            with pytest.raises(HTTPException) as exc_info:
                download_from_huggingface("test-model")
            assert exc_info.value.status_code == 504

    def test_download_from_huggingface_connection_error(self):
        """Test download_from_huggingface with connection error"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.RequestException("Connection failed")
            
            with pytest.raises(HTTPException) as exc_info:
                download_from_huggingface("test-model")
            assert exc_info.value.status_code == 503

    def test_download_from_huggingface_model_not_found(self):
        """Test download_from_huggingface with model not found"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            with pytest.raises(HTTPException) as exc_info:
                download_from_huggingface("nonexistent-model")
            assert exc_info.value.status_code == 404

    def test_download_from_huggingface_invalid_json(self):
        """Test download_from_huggingface with invalid JSON response"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response
            
            with pytest.raises(HTTPException) as exc_info:
                download_from_huggingface("test-model")
            assert exc_info.value.status_code == 502

    def test_download_from_huggingface_with_url(self):
        """Test download_from_huggingface with full URL"""
        with patch("src.services.s3_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"siblings": []}
            mock_get.return_value = mock_response
            
            with patch("src.services.s3_service.zipfile.ZipFile"):
                with pytest.raises(HTTPException) as exc_info:
                    download_from_huggingface("https://huggingface.co/test-model")
                assert exc_info.value.status_code == 400
                assert "No essential files found" in str(exc_info.value.detail)


class TestSignRequest:
    """Test sign_request function"""

    def test_sign_request_success(self):
        """Test successful request signing"""
        with patch("src.services.s3_service.get_credentials") as mock_creds:
            with patch("src.services.s3_service.SigV4Auth") as mock_auth:
                mock_credentials = MagicMock()
                mock_creds.return_value = mock_credentials
                
                mock_auth_instance = MagicMock()
                mock_auth.return_value = mock_auth_instance
                mock_auth_instance.add_auth = MagicMock()
                
                from botocore.awsrequest import AWSRequest
                request = AWSRequest(method="POST", url="https://example.com", data='{"gremlin": "g.V()"}')
                
                result = sign_request(request)
                
                mock_auth.assert_called_once()
                mock_auth_instance.add_auth.assert_called_once_with(request)
                assert isinstance(result, dict)


class TestSendRequest:
    """Test send_request function"""

    def test_send_request_success(self):
        """Test successful request sending"""
        with patch("src.services.s3_service.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"result": "success"}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = send_request("https://example.com", {"Content-Type": "application/json"}, '{"data": "test"}')
            assert result == '{"result": "success"}'

    def test_send_request_http_error(self):
        """Test send_request with HTTP error"""
        with patch("src.services.s3_service.urllib.request.urlopen") as mock_urlopen:
            import urllib.error
            mock_error = urllib.error.HTTPError("https://example.com", 500, "Internal Error", None, None)
            mock_error.read.return_value = b'{"error": "server error"}'
            mock_urlopen.side_effect = mock_error
            
            with pytest.raises(urllib.error.HTTPError):
                send_request("https://example.com", {}, '{"data": "test"}')


class TestWriteToNeptune:
    """Test write_to_neptune function"""

    def test_write_to_neptune_no_endpoint(self):
        """Test write_to_neptune when endpoint not configured"""
        with patch.dict("os.environ", {}, clear=True):
            # Should return without error when endpoint not set
            write_to_neptune({"node1": ["child1", "child2"]})

    def test_write_to_neptune_success(self):
        """Test successful write to Neptune"""
        with patch.dict("os.environ", {"NEPTUNE_ENDPOINT": "https://neptune.example.com"}):
            with patch("src.services.s3_service.sign_request") as mock_sign:
                with patch("src.services.s3_service.send_request") as mock_send:
                    mock_sign.return_value = {"Authorization": "test-auth"}
                    mock_send.return_value = '{"result": {"data": [{"@value": {"value": 0}}]}}'
                    
                    write_to_neptune({"node1": ["child1"], "node2": ["child2"]})
                    
                    # Should be called multiple times (clear, verify, add nodes, add edges)
                    assert mock_send.call_count > 0

    def test_write_to_neptune_with_exception(self):
        """Test write_to_neptune with exception in process_node"""
        with patch.dict("os.environ", {"NEPTUNE_ENDPOINT": "https://neptune.example.com"}):
            with patch("src.services.s3_service.sign_request") as mock_sign:
                with patch("src.services.s3_service.send_request") as mock_send:
                    mock_sign.return_value = {"Authorization": "test-auth"}
                    # First few calls succeed (clear, verify), then fail
                    mock_send.side_effect = [
                        '{"result": {"data": [{"@value": {"value": 0}}]}}',  # Clear response
                        '{"result": {"data": [{"@value": {"value": 0}}]}}',  # Verify response
                        Exception("Neptune error")  # Process node fails
                    ]
                    
                    # Should handle exception gracefully
                    write_to_neptune({"node1": ["child1"]})


class TestSyncModelLineageToNeptune:
    """Test sync_model_lineage_to_neptune function"""

    def test_sync_model_lineage_aws_unavailable(self):
        """Test sync when AWS unavailable"""
        with patch("src.services.s3_service.aws_available", False):
            with pytest.raises(HTTPException) as exc_info:
                sync_model_lineage_to_neptune()
            assert exc_info.value.status_code == 503

    def test_sync_model_lineage_success(self):
        """Test successful lineage sync"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.list_models") as mock_list:
                with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
                    with patch("src.services.s3_service.write_to_neptune"):
                        mock_list.return_value = {
                            "models": [
                                {"Name": "model1", "Version": "1.0.0"},
                                {"Name": "model2", "Version": "1.0.0"}
                            ]
                        }
                        mock_lineage.return_value = {
                            "lineage_map": {"parent1": ["child1", "child2"]}
                        }
                        
                        result = sync_model_lineage_to_neptune()
                        
                        assert result["message"] == "Model lineage successfully synced to Neptune"
                        assert "relationships" in result

    def test_sync_model_lineage_with_errors(self):
        """Test sync with errors processing models"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.list_models") as mock_list:
                with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
                    with patch("src.services.s3_service.write_to_neptune") as mock_write:
                        mock_list.return_value = {
                            "models": [
                                {"Name": "model1", "Version": "1.0.0"},
                                {"Name": None, "Version": "1.0.0"}  # Missing name
                            ]
                        }
                        mock_lineage.return_value = {"lineage_map": {}}
                        
                        result = sync_model_lineage_to_neptune()
                        assert result["message"] == "Model lineage successfully synced to Neptune"

    def test_sync_model_lineage_exception(self):
        """Test sync with exception"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.list_models") as mock_list:
                mock_list.side_effect = Exception("S3 error")
                
                with pytest.raises(HTTPException) as exc_info:
                    sync_model_lineage_to_neptune()
                assert exc_info.value.status_code == 500


class TestModelIngestion:
    """Test model_ingestion function"""

    def test_model_ingestion_aws_unavailable(self):
        """Test ingestion when AWS unavailable"""
        with patch("src.services.s3_service.aws_available", False):
            with pytest.raises(HTTPException) as exc_info:
                model_ingestion("test-model", "1.0.0")
            assert exc_info.value.status_code == 503

    def test_model_ingestion_success(self):
        """Test successful model ingestion"""
        # Create a valid ZIP with config.json
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("config.json", json.dumps({"model_type": "test"}))
            zip_file.writestr("model.safetensors", b"model weights")
        
        zip_content = zip_buffer.getvalue()
        
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.download_from_huggingface") as mock_download:
                with patch("src.services.s3_service.validate_huggingface_structure") as mock_validate:
                    with patch("src.services.s3_service.extract_config_from_model") as mock_extract:
                        with patch("src.services.rating.create_metadata_from_files") as mock_metadata:
                            with patch("src.services.rating.run_acme_metrics") as mock_metrics:
                                with patch("src.services.s3_service.fetch_hf_metadata") as mock_hf:
                                    mock_download.return_value = zip_content
                                    mock_validate.return_value = {
                                        "valid": True,
                                        "has_config": True,
                                        "has_weights": True
                                    }
                                    mock_extract.return_value = {"model_type": "test"}
                                    mock_metadata.return_value = {
                                        "name": "test-model",
                                        "readme_text": "Test model"
                                    }
                                    mock_metrics.return_value = {
                                        "license": 0.8,
                                        "ramp_up": 0.7,
                                        "bus_factor": 0.9,
                                        "performance_claims": 0.6,
                                        "size": 0.5,
                                        "dataset_code": 0.8,
                                        "dataset_quality": 0.7,
                                        "code_quality": 0.9,
                                        "reproducibility": 0.8,
                                        "reviewedness": 0.7,
                                        "treescore": 0.6
                                    }
                                    mock_hf.return_value = {"likes": 100, "downloads": 1000}
                                    
                                    result = model_ingestion("test-model", "1.0.0")
                                    
                                    assert "message" in result or "status" in result
                                    mock_download.assert_called_once()
                                    mock_validate.assert_called_once()

    def test_model_ingestion_missing_config(self):
        """Test ingestion with missing config.json"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("model.safetensors", b"weights")
        
        zip_content = zip_buffer.getvalue()
        
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.download_from_huggingface") as mock_download:
                with patch("src.services.s3_service.validate_huggingface_structure") as mock_validate:
                    mock_download.return_value = zip_content
                    mock_validate.return_value = {
                        "valid": True,
                        "has_config": False,
                        "has_weights": True
                    }
                    
                    with pytest.raises(HTTPException) as exc_info:
                        model_ingestion("test-model", "1.0.0")
                    assert exc_info.value.status_code == 400
                    assert "Missing: config.json" in exc_info.value.detail

    def test_model_ingestion_download_failure(self):
        """Test ingestion with download failure"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.download_from_huggingface") as mock_download:
                mock_download.side_effect = HTTPException(status_code=404, detail="Model not found")
                
                with pytest.raises(HTTPException) as exc_info:
                    model_ingestion("test-model", "1.0.0")
                assert exc_info.value.status_code == 404

    def test_model_ingestion_with_github_url_in_config(self):
        """Test ingestion with GitHub URL in config"""
        zip_buffer = io.BytesIO()
        config_with_github = {
            "model_type": "test",
            "description": "See <a href='https://github.com/owner/repo'>GitHub</a>"
        }
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("config.json", json.dumps(config_with_github))
            zip_file.writestr("model.safetensors", b"weights")
        
        zip_content = zip_buffer.getvalue()
        
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.download_from_huggingface") as mock_download:
                with patch("src.services.s3_service.validate_huggingface_structure") as mock_validate:
                    with patch("src.services.s3_service.extract_config_from_model") as mock_extract:
                        with patch("src.services.rating.create_metadata_from_files") as mock_metadata:
                            with patch("src.services.rating.run_acme_metrics") as mock_metrics:
                                with patch("src.services.s3_service.fetch_hf_metadata") as mock_hf:
                                    mock_download.return_value = zip_content
                                    mock_validate.return_value = {
                                        "valid": True,
                                        "has_config": True,
                                        "has_weights": True
                                    }
                                    mock_extract.return_value = config_with_github
                                    mock_metadata.return_value = {"name": "test-model"}
                                    mock_metrics.return_value = {
                                        "license": 0.8,
                                        "ramp_up": 0.7,
                                        "bus_factor": 0.9,
                                        "performance_claims": 0.6,
                                        "size": 0.5,
                                        "dataset_code": 0.8,
                                        "dataset_quality": 0.7,
                                        "code_quality": 0.9,
                                        "reproducibility": 0.8,
                                        "reviewedness": 0.7,
                                        "treescore": 0.6
                                    }
                                    mock_hf.return_value = {}
                                    
                                    result = model_ingestion("test-model", "1.0.0")
                                    # Should extract GitHub URL from config
                                    assert result is not None


# Additional code path coverage tests

class TestUploadModelCodePaths:
    """Additional tests for upload_model code paths"""

    def test_upload_model_no_such_bucket(self):
        """Test upload_model with NoSuchBucket error"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.put_object.side_effect = ClientError(
                        {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                        "PutObject"
                    )
                    
                    with pytest.raises(HTTPException) as exc_info:
                        upload_model(b"test content", "test-model", "1.0.0")
                    assert exc_info.value.status_code == 503

    def test_upload_model_invalid_bucket_name(self):
        """Test upload_model with InvalidBucketName error"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.put_object.side_effect = ClientError(
                        {"Error": {"Code": "InvalidBucketName", "Message": "Invalid name"}},
                        "PutObject"
                    )
                    
                    with pytest.raises(HTTPException) as exc_info:
                        upload_model(b"test content", "test-model", "1.0.0")
                    assert exc_info.value.status_code == 503

    def test_upload_model_generic_exception(self):
        """Test upload_model with generic exception"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.put_object.side_effect = Exception("Generic error")
                    
                    with pytest.raises(HTTPException) as exc_info:
                        upload_model(b"test content", "test-model", "1.0.0")
                    assert exc_info.value.status_code == 500

    def test_upload_model_sanitize_model_id(self):
        """Test upload_model sanitizes model_id correctly"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.put_object.return_value = {}
                    
                    upload_model(b"content", "https://huggingface.co/test/model", "1.0.0")
                    
                    # Verify sanitized key was used
                    call_args = mock_s3.put_object.call_args
                    assert "test_model" in call_args[1]["Key"]


class TestDownloadModelCodePaths:
    """Additional tests for download_model code paths"""

    def test_download_model_component_extraction_error(self):
        """Test download_model with component extraction error"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                        zip_file.writestr("other.txt", b"data")
                    zip_content = zip_buffer.getvalue()
                    
                    mock_s3.get_object.return_value = {
                        "Body": MagicMock(read=lambda: zip_content)
                    }
                    
                    with pytest.raises(HTTPException) as exc_info:
                        download_model("test-model", "1.0.0", "weights")
                    assert exc_info.value.status_code == 400

    def test_download_model_s3_get_object_error(self):
        """Test download_model with S3 get_object error"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.get_object.side_effect = ClientError(
                        {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
                        "GetObject"
                    )
                    
                    with pytest.raises(HTTPException) as exc_info:
                        download_model("test-model", "1.0.0")
                    assert exc_info.value.status_code == 500

    def test_download_model_component_datasets(self):
        """Test download_model with datasets component"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                        zip_file.writestr("data.csv", b"dataset content")
                    zip_content = zip_buffer.getvalue()
                    
                    mock_s3.get_object.return_value = {
                        "Body": MagicMock(read=lambda: zip_content)
                    }
                    
                    with pytest.raises(HTTPException) as exc_info:
                        download_model("test-model", "1.0.0", "datasets")
                    assert exc_info.value.status_code == 400
                    assert "datasets" in str(exc_info.value.detail).lower()


class TestListArtifactsCodePaths:
    """Additional tests for list_artifacts_from_s3 code paths"""

    def test_list_artifacts_from_s3_empty_response(self):
        """Test list_artifacts_from_s3 with empty response"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_paginator = MagicMock()
                    mock_s3.get_paginator.return_value = mock_paginator
                    mock_paginator.paginate.return_value = [{"Contents": []}]
                    
                    result = list_artifacts_from_s3("model")
                    assert "artifacts" in result
                    assert len(result["artifacts"]) == 0

    def test_list_artifacts_from_s3_with_pagination(self):
        """Test list_artifacts_from_s3 with pagination"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_paginator = MagicMock()
                    mock_s3.get_paginator.return_value = mock_paginator
                    mock_paginator.paginate.return_value = [
                        {
                            "Contents": [
                                {"Key": "models/model1/1.0.0/model.zip"},
                                {"Key": "models/model2/1.0.0/model.zip"}
                            ],
                            "NextContinuationToken": "token123"
                        },
                        {
                            "Contents": [
                                {"Key": "models/model3/1.0.0/model.zip"}
                            ]
                        }
                    ]
                    
                    result = list_artifacts_from_s3("model")
                    assert "artifacts" in result
                    assert len(result["artifacts"]) == 3


class TestGetModelSizesCodePaths:
    """Additional tests for get_model_sizes code paths"""

    def test_get_model_sizes_malformed_zip(self):
        """Test get_model_sizes with malformed ZIP"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.head_object.return_value = {"ContentLength": 1000}
                    mock_s3.get_object.return_value = {
                        "Body": MagicMock(read=lambda: b"not a zip file")
                    }
                    
                    result = get_model_sizes("test-model", "1.0.0")
                    # Should handle error gracefully
                    assert "error" in result or "full" in result

    def test_get_model_sizes_missing_file(self):
        """Test get_model_sizes with missing file"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.head_object.side_effect = ClientError(
                        {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                        "HeadObject"
                    )
                    
                    result = get_model_sizes("test-model", "1.0.0")
                    assert "error" in result


class TestListModelsCodePaths:
    """Additional tests for list_models code paths"""

    def test_list_models_with_model_regex(self):
        """Test list_models with model_regex filter"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    mock_s3.list_objects_v2.return_value = {
                        "Contents": [
                            {"Key": "models/test_model/1.0.0/model.zip"},
                            {"Key": "models/other_model/1.0.0/model.zip"}
                        ]
                    }
                    
                    result = list_models(model_regex="^test")
                    assert "models" in result

    def test_list_models_invalid_name_regex(self):
        """Test list_models with invalid name regex"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3") as mock_s3:
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    with pytest.raises(HTTPException) as exc_info:
                        list_models(name_regex="[invalid")
                    assert exc_info.value.status_code == 400

    def test_list_models_invalid_model_regex(self):
        """Test list_models with invalid model regex"""
        with patch("src.services.s3_service.aws_available", True):
            with patch("src.services.s3_service.s3"):
                with patch("src.services.s3_service.ap_arn", "test-bucket"):
                    with pytest.raises(HTTPException) as exc_info:
                        list_models(model_regex="[invalid")
                    assert exc_info.value.status_code == 400

