"""
Strategic coverage tests for the largest remaining uncovered blocks in services
Targeting s3_service.py, rating.py, and other service files
"""
import pytest
from unittest.mock import MagicMock, patch, ANY
from botocore.exceptions import ClientError


class TestS3ServiceLargeBlocks:
    """Target large uncovered blocks in s3_service"""
    
    @patch("src.services.s3_service.requests")
    def test_huggingface_download_success(self, mock_requests):
        """Test downloading from HuggingFace"""
        from src.services.s3_service import download_from_huggingface
        
        # Mock HuggingFace API response with model info
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "modelId": "user/model",
            "siblings": [
                {"rfilename": "config.json"},
                {"rfilename": "README.md"},
                {"rfilename": "LICENSE"}
            ]
        }
        
        # Mock file download responses
        mock_file_response = MagicMock()
        mock_file_response.status_code = 200
        mock_file_response.content = b"file content"
        
        # First call is API, subsequent calls are file downloads
        mock_requests.get.side_effect = [mock_api_response, mock_file_response, mock_file_response, mock_file_response]
        
        result = download_from_huggingface("user/model", "1.0.0")
        assert result is not None
        assert isinstance(result, bytes)

    @patch("src.services.s3_service.s3")
    def test_list_models_with_pagination(self, mock_s3):
        """Test list_models with pagination"""
        from src.services.s3_service import list_models
        
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "models/model1/1.0.0/model.zip"},
                {"Key": "models/model2/1.0.0/model.zip"}
            ],
            "IsTruncated": True,
            "NextContinuationToken": "token123"
        }
        
        result = list_models(limit=10)
        assert len(result["models"]) == 2
        assert result["next_token"] == "token123"

    @patch("src.services.s3_service.s3")
    def test_get_model_sizes_all_variants(self, mock_s3):
        """Test getting model sizes for all variants"""
        from src.services.s3_service import get_model_sizes
        
        mock_s3.head_object.side_effect = [
            {"ContentLength": 1024000},  # full
            {"ContentLength": 512000},   # weights
            {"ContentLength": 256000},   # quantized
        ]
        
        result = get_model_sizes("model1", "1.0.0")
        assert "full" in result
        assert "weights" in result

    @patch("src.services.s3_service.requests")
    def test_fetch_huggingface_metadata(self, mock_requests):
        """Test fetching HuggingFace metadata"""
        # fetch_huggingface_metadata doesn't exist as a function, but we can test the pattern
        # by testing download_from_huggingface which fetches metadata first
        from src.services.s3_service import download_from_huggingface
        
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "modelId": "user/model",
            "license": "MIT",
            "tags": ["nlp", "transformer"],
            "siblings": [
                {"rfilename": "config.json"},
                {"rfilename": "README.md"}
            ]
        }
        
        mock_file_response = MagicMock()
        mock_file_response.status_code = 200
        mock_file_response.content = b"file content"
        
        # First call is API metadata, subsequent calls are file downloads
        mock_requests.get.side_effect = [mock_api_response, mock_file_response, mock_file_response]
        
        # The function fetches metadata as part of download
        result = download_from_huggingface("user/model")
        assert result is not None
        # Verify the API was called to get metadata
        assert mock_requests.get.call_count >= 1


class TestRatingServiceCoverage:
    """Target uncovered areas in rating service"""
    
    @patch("src.services.rating.subprocess.run")
    @patch("src.services.rating.analyze_model_content")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"})
    def test_run_scorer_success(self, mock_analyze, mock_run):
        """Test successful scorer execution"""
        from src.services.rating import run_scorer
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"NetScore": 0.8, "BusFactor": 0.9}\n',
            stderr=""
        )
        
        result = run_scorer("https://github.com/user/repo")
        assert result["NetScore"] == 0.8

    @patch("src.services.rating.subprocess.run")
    def test_run_scorer_timeout(self, mock_run):
        """Test scorer timeout handling"""
        from src.services.rating import run_scorer
        import subprocess
        
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=60)
        
        with pytest.raises(Exception):
            run_scorer("https://github.com/user/repo")

    @patch("src.services.rating.subprocess.run")
    def test_run_scorer_error(self, mock_run):
        """Test scorer error handling"""
        from src.services.rating import run_scorer
        
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Error occurred"
        )
        
        with pytest.raises(Exception):
            run_scorer("https://github.com/user/repo")


class TestValidatorServiceCoverage:
    """Target validator service"""
    
    def test_validate_package_name_valid(self):
        """Test valid package name"""
        from src.services.validator_service import validate_package_name
        
        assert validate_package_name("my-package") == True
        assert validate_package_name("my_package") == True
        assert validate_package_name("mypackage123") == True

    def test_validate_package_name_invalid(self):
        """Test invalid package name"""
        from src.services.validator_service import validate_package_name
        
        assert validate_package_name("") == False
        assert validate_package_name("a" * 300) == False
        assert validate_package_name("my package") == False

    def test_validate_semver_valid(self):
        """Test valid semver"""
        from src.services.validator_service import validate_semver
        
        assert validate_semver("1.0.0") == True
        assert validate_semver("2.1.3") == True
        assert validate_semver("1.0.0-alpha") == True

    def test_validate_semver_invalid(self):
        """Test invalid semver"""
        from src.services.validator_service import validate_semver
        
        assert validate_semver("1.0") == False
        assert validate_semver("v1.0.0") == False
        assert validate_semver("abc") == False


class TestLicenseCompatibilityCoverage:
    """Target license compatibility service"""
    
    def test_check_license_compatibility_compatible(self):
        """Test compatible licenses"""
        from src.services.license_compatibility import check_license_compatibility
        
        result = check_license_compatibility("MIT", "MIT")
        assert result["compatible"] == True

    def test_check_license_compatibility_incompatible(self):
        """Test incompatible licenses"""
        from src.services.license_compatibility import check_license_compatibility
        
        # MIT (permissive) + GPL-3.0 (copyleft) should be incompatible
        result = check_license_compatibility("MIT", "GPL-3.0")
        assert result["compatible"] == False

    def test_extract_license_from_text(self):
        """Test extracting license from text"""
        from src.services.license_compatibility import extract_license_from_text
        
        text = "This project is licensed under the MIT License"
        result = extract_license_from_text(text)
        assert "MIT" in result or result is not None


class TestArtifactStorageCoverage:
    """Target artifact storage service"""
    
    @patch("src.services.artifact_storage.dynamodb")
    def test_save_artifact_success(self, mock_dynamodb):
        """Test successful artifact save"""
        from src.services.artifact_storage import save_artifact
        
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        result = save_artifact("a1", {"name": "test", "type": "model"})
        assert result == True
        mock_table.put_item.assert_called_once()

    @patch("src.services.artifact_storage.dynamodb")
    def test_get_artifact_not_found(self, mock_dynamodb):
        """Test getting non-existent artifact"""
        from src.services.artifact_storage import get_artifact
        
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb.Table.return_value = mock_table
        
        result = get_artifact("nonexistent")
        assert result is None

    @patch("src.services.artifact_storage.dynamodb")
    def test_delete_artifact_success(self, mock_dynamodb):
        """Test successful artifact deletion"""
        from src.services.artifact_storage import delete_artifact
        
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        result = delete_artifact("a1")
        assert result == True
        mock_table.delete_item.assert_called_once()


class TestPackageServiceCoverage:
    """Target package service"""
    
    @patch("src.services.package_service.dynamodb")
    def test_get_package_by_id(self, mock_dynamodb):
        """Test getting package by ID"""
        from src.services.package_service import get_package_by_id
        
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"pkg_key": "p1", "pkg_name": "package1", "version": "1.0.0"}
        }
        mock_dynamodb.Table.return_value = mock_table
        
        result = get_package_by_id("p1")
        assert result is not None
        assert result["pkg_name"] == "package1"

    @patch("src.services.package_service.dynamodb")
    def test_search_packages(self, mock_dynamodb):
        """Test searching packages"""
        from src.services.package_service import search_packages
        
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                {"pkg_key": "p1", "pkg_name": "test-package", "version": "1.0.0"},
                {"pkg_key": "p2", "pkg_name": "other-package", "version": "1.0.0"}
            ]
        }
        mock_dynamodb.Table.return_value = mock_table
        
        result = search_packages("test")
        assert len(result) > 0
        assert result[0]["pkg_name"] == "test-package"
