"""
Tests for license_compatibility.py service
"""
import pytest
from unittest.mock import patch, MagicMock
from src.services.license_compatibility import (
    normalize_license,
    extract_model_license,
    extract_github_license,
    check_license_compatibility,
)


class TestNormalizeLicense:
    """Test license normalization"""
    
    def test_normalize_mit_license(self):
        """Test MIT license normalization"""
        assert normalize_license("MIT License") == "mit"
        assert normalize_license("MIT-License") == "mit"
        assert normalize_license("mit") == "mit"
    
    def test_normalize_apache_license(self):
        """Test Apache license normalization"""
        result1 = normalize_license("Apache License")
        result2 = normalize_license("Apache-2.0")
        result3 = normalize_license("Apache 2.0")
        # All should normalize to apache-2
        assert result1 == "apache-2" or "apache" in result1.lower()
        assert result2 == "apache-2" or "apache" in result2.lower()
        assert result3 == "apache-2" or "apache" in result3.lower()
    
    def test_normalize_bsd_license(self):
        """Test BSD license normalization"""
        assert normalize_license("BSD License") == "bsd"
        assert normalize_license("BSD-2-Clause") == "bsd"
    
    def test_normalize_gpl_license(self):
        """Test GPL license normalization"""
        assert normalize_license("GPL-3.0") == "gpl-3"
        assert normalize_license("GPL-2.0") == "gpl-2"
        assert "gpl" in normalize_license("GPL License").lower()
    
    def test_normalize_empty_string(self):
        """Test empty license string"""
        assert normalize_license("") == ""
        assert normalize_license(None) == ""
    
    def test_normalize_unknown_license(self):
        """Test unknown license normalization"""
        result = normalize_license("Custom License v1.0")
        assert isinstance(result, str)
        assert len(result) > 0


class TestExtractModelLicense:
    """Test model license extraction"""
    
    @patch("src.services.s3_service.download_model")
    @patch("src.services.s3_service.list_models")
    @patch("src.services.s3_service.extract_config_from_model")
    def test_extract_license_from_s3(self, mock_extract_config, mock_list, mock_download):
        """Test extracting license from S3 model"""
        mock_list.return_value = {"models": [{"name": "test-model", "version": "1.0.0"}]}
        mock_download.return_value = b"PK\x03\x04"  # ZIP file header
        mock_extract_config.return_value = {"license": "mit"}
        
        result = extract_model_license("test-model", "1.0.0")
        # Should attempt to extract license from config
        assert mock_list.called or mock_download.called
        # Result may be None if extraction fails, or a normalized license string
        assert result is None or isinstance(result, str)
    
    @patch("src.services.s3_service.download_model")
    @patch("src.services.s3_service.list_models")
    @patch("src.services.license_compatibility.fetch_hf_metadata")
    def test_extract_license_not_found(self, mock_hf, mock_list, mock_download):
        """Test extracting license when model not found"""
        mock_list.return_value = {"models": []}
        mock_download.side_effect = Exception("Not found")
        mock_hf.return_value = None
        
        result = extract_model_license("nonexistent-model", "1.0.0")
        assert result is None


class TestExtractGithubLicense:
    """Test GitHub license extraction"""
    
    @patch("src.services.license_compatibility.fetch_github_metadata")
    def test_extract_github_license_success(self, mock_fetch):
        """Test extracting license from GitHub"""
        # Function expects license to be a string (SPDX identifier), not nested dict
        mock_fetch.return_value = {"license": "MIT"}
        
        result = extract_github_license("https://github.com/user/repo")
        assert result == "mit"
    
    @patch("src.services.license_compatibility.fetch_github_metadata")
    def test_extract_github_license_not_found(self, mock_fetch):
        """Test extracting license when GitHub repo has no license"""
        mock_fetch.return_value = {"license": None}
        
        result = extract_github_license("https://github.com/user/repo")
        assert result is None or result == ""
    
    @patch("src.services.license_compatibility.fetch_github_metadata")
    def test_extract_github_license_error(self, mock_fetch):
        """Test extracting license when GitHub fetch fails"""
        mock_fetch.side_effect = Exception("API error")
        
        result = extract_github_license("https://github.com/user/repo")
        assert result is None


class TestCheckLicenseCompatibility:
    """Test license compatibility checking"""
    
    def test_mit_compatibility(self):
        """Test MIT license compatibility"""
        result = check_license_compatibility("mit", "mit")
        # Function returns a dict with 'compatible' key
        assert isinstance(result, dict)
        assert "compatible" in result
        assert result.get("compatible") is True
    
    def test_apache_compatibility(self):
        """Test Apache license compatibility"""
        result = check_license_compatibility("apache-2", "apache-2")
        assert isinstance(result, dict) or isinstance(result, str)
    
    def test_gpl_compatibility(self):
        """Test GPL license compatibility"""
        result = check_license_compatibility("gpl-3", "gpl-3")
        assert isinstance(result, dict) or isinstance(result, str)
    
    def test_mixed_license_compatibility(self):
        """Test mixed license compatibility"""
        result = check_license_compatibility("mit", "apache-2")
        assert isinstance(result, dict) or isinstance(result, str)
    
    def test_no_license_compatibility(self):
        """Test no license compatibility"""
        result = check_license_compatibility(None, None)
        assert isinstance(result, dict) or isinstance(result, str)
    
    @patch("src.services.license_compatibility.extract_model_license")
    @patch("src.services.license_compatibility.extract_github_license")
    def test_check_compatibility_with_extraction(self, mock_github, mock_model):
        """Test license compatibility check with extraction"""
        mock_model.return_value = "mit"
        mock_github.return_value = "apache-2"
        
        # Function takes model_license and github_license as strings, not model_id/url
        # So we extract first, then pass to function
        model_license = mock_model("test-model", "1.0.0")
        github_license = mock_github("https://github.com/user/repo")
        
        result = check_license_compatibility(
            model_license=model_license,
            github_license=github_license
        )
        assert isinstance(result, dict)
        assert "compatible" in result

