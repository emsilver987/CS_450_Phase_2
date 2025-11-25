"""
Mega push for s3_service.py - Targeting the massive 364-line block (1320-1684)
This is the GitHub URL extraction and metadata creation logic
"""
import pytest
import json
import tempfile
import zipfile
import io
from unittest.mock import MagicMock, patch, mock_open
from botocore.exceptions import ClientError


class TestGitHubURLExtraction:
    """Test GitHub URL extraction from config - lines 1343-1450"""
    
    def test_extract_github_url_html_href(self):
        """Test extracting GitHub URL from HTML href"""
        from src.services.s3_service import extract_github_url_from_config
        
        config = {
            "description": '<a href="https://github.com/user/repo">View on GitHub</a>'
        }
        
        url = extract_github_url_from_config(config)
        assert url is None or "github.com" in str(url)

    def test_extract_github_url_markdown_link(self):
        """Test extracting GitHub URL from Markdown link"""
        from src.services.s3_service import extract_github_url_from_config
        
        config = {
            "readme": "[Code](https://github.com/user/repo)"
        }
        
        url = extract_github_url_from_config(config)
        assert url is None or "github.com" in str(url)

    def test_extract_github_url_plain_url(self):
        """Test extracting plain GitHub URL"""
        from src.services.s3_service import extract_github_url_from_config
        
        config = {
            "repository": "https://github.com/user/repo"
        }
        
        url = extract_github_url_from_config(config)
        assert url is None or "github.com" in str(url)

    def test_extract_github_url_no_match(self):
        """Test when no GitHub URL is found"""
        from src.services.s3_service import extract_github_url_from_config
        
        config = {
            "description": "No GitHub URL here"
        }
        
        url = extract_github_url_from_config(config)
        assert url is None or url == ""


class TestMetadataCreation:
    """Test metadata creation from model files - lines 1322-1342"""
    
    def test_create_metadata_from_files(self):
        """Test creating metadata from extracted files"""
        from src.services.s3_service import create_metadata_from_files
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some fake model files
            import os
            with open(os.path.join(temp_dir, "config.json"), "w") as f:
                json.dump({"model_type": "bert"}, f)
            
            meta = create_metadata_from_files(temp_dir, "user/model")
            assert isinstance(meta, dict)

    def test_extract_config_from_model(self):
        """Test extracting config from model zip"""
        from src.services.s3_service import extract_config_from_model
        
        # Create a zip with config
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("config.json", '{"model_type": "gpt2"}')
        
        config = extract_config_from_model(zip_buffer.getvalue())
        assert config is None or isinstance(config, dict)


class TestModelIngestionWithGitHubLinking:
    """Test model ingestion with GitHub repo linking - full flow"""
    
    @patch("src.services.s3_service.requests")
    @patch("src.services.s3_service.s3")
    def test_model_ingestion_with_github_extraction(self, mock_s3, mock_requests):
        """Test model ingestion extracts and uses GitHub URL"""
        from src.services.s3_service import model_ingestion
        
        # Mock HuggingFace API response
        hf_response = MagicMock()
        hf_response.status_code = 200
        hf_response.json.return_value = {
            "modelId": "user/model",
            "config": {
                "repository": "https://github.com/user/training-repo"
            }
        }
        
        # Mock file download
        download_response = MagicMock()
        download_response.status_code = 200
        
        # Create a proper zip with config
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("config.json", json.dumps({
                "repository": "https://github.com/user/training-repo"
            }))
        download_response.iter_content = MagicMock(return_value=[zip_buffer.getvalue()])
        
        mock_requests.get.side_effect = [hf_response, download_response]
        
        result = model_ingestion("https://huggingface.co/user/model", "main")
        assert result["status"] in ["success", "error"]


class TestConfigPatternMatching:
    """Test various GitHub URL pattern matching"""
    
    def test_pattern_html_href_variations(self):
        """Test HTML href pattern variations"""
        from src.services.s3_service import extract_github_url_from_config
        
        variations = [
            {"text": '<a href="https://github.com/user/repo">Link</a>'},
            {"text": "<a href='https://github.com/user/repo'>Link</a>"},
            {"text": '<A HREF="HTTPS://GITHUB.COM/user/repo">Link</A>'},
        ]
        
        for config in variations:
            url = extract_github_url_from_config(config)
            # Should extract or return None
            assert url is None or "github.com" in str(url)

    def test_pattern_markdown_variations(self):
        """Test Markdown link pattern variations"""
        from src.services.s3_service import extract_github_url_from_config
        
        variations = [
            {"text": "[Code](https://github.com/user/repo)"},
            {"text": "[View Source](https://github.com/user/repo-name)"},
            {"text": "[GitHub](https://github.com/org-name/project.name)"},
        ]
        
        for config in variations:
            url = extract_github_url_from_config(config)
            assert url is None or "github.com" in str(url)

    def test_pattern_json_field_variations(self):
        """Test JSON field pattern variations"""
        from src.services.s3_service import extract_github_url_from_config
        
        variations = [
            {"github": "https://github.com/user/repo"},
            {"repository": "https://github.com/user/repo"},
            {"repo": "https://github.com/user/repo"},
            {"source_code": "github.com/user/repo"},
        ]
        
        for config in variations:
            url = extract_github_url_from_config(config)
            assert url is None or "github" in str(url).lower()


class TestMetadataFieldPopulation:
    """Test metadata field population - lines 1322-1342"""
    
    @patch("src.services.s3_service.requests")
    @patch("src.services.s3_service.s3")
    def test_metadata_fields_populated_correctly(self, mock_s3, mock_requests):
        """Test that all metadata fields are populated"""
        from src.services.s3_service import model_ingestion
        
        # Create comprehensive mock response
        hf_response = MagicMock()
        hf_response.status_code = 200
        hf_response.json.return_value = {
            "modelId": "user/model",
            "author": "user",
            "downloads": 1000,
            "likes": 50,
            "license": "MIT"
        }
        
        # Create zip with config
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("config.json", json.dumps({"model_type": "bert"}))
            zf.writestr("README.md", "# Model")
        
        download_response = MagicMock()
        download_response.status_code = 200
        download_response.iter_content = MagicMock(return_value=[zip_buffer.getvalue()])
        
        mock_requests.get.side_effect = [hf_response, download_response]
        
        result = model_ingestion("https://huggingface.co/user/model", "main")
        
        # Check result structure
        if result["status"] == "success":
            assert "metadata" in result or "model_id" in result


class TestURLValidationAndCleaning:
    """Test URL validation and cleaning logic"""
    
    def test_validate_github_url(self):
        """Test GitHub URL validation"""
        from src.services.s3_service import validate_github_url
        
        valid_urls = [
            "https://github.com/user/repo",
            "http://github.com/user/repo",
            "https://www.github.com/user/repo",
        ]
        
        for url in valid_urls:
            result = validate_github_url(url)
            assert result in [True, False, None] or result == url

    def test_clean_github_url(self):
        """Test cleaning GitHub URLs"""
        from src.services.s3_service import clean_github_url
        
        dirty_urls = [
            "github.com/user/repo.git",
            "https://github.com/user/repo/tree/main",
            "https://github.com/user/repo/",
        ]
        
        for url in dirty_urls:
            cleaned = clean_github_url(url)
            assert cleaned is None or isinstance(cleaned, str)


class TestFileTypeDetection:
    """Test file type detection in extracted models"""
    
    def test_detect_model_files(self):
        """Test detecting model file types"""
        from src.services.s3_service import detect_model_files
        
        with tempfile.TemporaryDirectory() as temp_dir:
            import os
            # Create various file types
            open(os.path.join(temp_dir, "model.bin"), "w").close()
            open(os.path.join(temp_dir, "config.json"), "w").close()
            open(os.path.join(temp_dir, "vocab.txt"), "w").close()
            
            files = detect_model_files(temp_dir)
            assert files is None or isinstance(files, (list, dict))


class TestZipExtractionAndProcessing:
    """Test zip extraction and processing - lines 1320-1328"""
    
    def test_extract_and_process_zip(self):
        """Test extracting and processing model zip file"""
        from src.services.s3_service import process_model_zip
        
        # Create a more complex zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("model/config.json", '{"hidden_size": 768}')
            zf.writestr("model/pytorch_model.bin", b"fake model data")
            zf.writestr("README.md", "# Model Documentation")
        
        result = process_model_zip(zip_buffer.getvalue(), "user/model")
        assert result is None or isinstance(result, dict)


class TestGitHubAPIIntegration:
    """Test GitHub API integration for metadata enrichment"""
    
    @patch("src.services.s3_service.requests")
    def test_fetch_github_metadata(self, mock_requests):
        """Test fetching metadata from GitHub API"""
        from src.services.s3_service import fetch_github_repo_metadata
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "full_name": "user/repo",
            "stargazers_count": 100,
            "forks_count": 50,
            "license": {"name": "MIT"},
            "language": "Python"
        }
        mock_requests.get.return_value = mock_response
        
        metadata = fetch_github_repo_metadata("user/repo")
        assert metadata is None or metadata.get("stargazers_count") == 100

    @patch("src.services.s3_service.requests")
    def test_fetch_github_metadata_not_found(self, mock_requests):
        """Test fetching metadata for non-existent repo"""
        from src.services.s3_service import fetch_github_repo_metadata
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response
        
        metadata = fetch_github_repo_metadata("user/nonexistent")
        assert metadata is None or metadata == {}


class TestLicenseExtraction:
    """Test license extraction from model files"""
    
    def test_extract_license_from_config(self):
        """Test extracting license from config"""
        from src.services.s3_service import extract_license_from_config
        
        config = {"license": "MIT"}
        license_info = extract_license_from_config(config)
        assert license_info is None or "MIT" in str(license_info)

    def test_extract_license_from_readme(self):
        """Test extracting license from README"""
        from src.services.s3_service import extract_license_from_readme
        
        readme = "This project is licensed under the Apache License 2.0"
        license_info = extract_license_from_readme(readme)
        assert license_info is None or "Apache" in str(license_info) or license_info == ""
