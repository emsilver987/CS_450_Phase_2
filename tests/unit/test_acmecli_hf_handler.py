"""
Unit tests for acmecli HuggingFace handler
"""
import json
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
import pytest

from src.acmecli.hf_handler import HFHandler, fetch_hf_metadata


class TestHFHandlerInit:
    """Test HFHandler initialization"""

    def test_init(self):
        """Test handler initialization"""
        handler = HFHandler()
        assert handler._headers == {"User-Agent": "ACME-CLI/1.0"}


class TestHFHandlerCategorizeUrl:
    """Test _categorize_url method"""

    def test_categorize_github_url(self):
        """Test categorizing GitHub URL"""
        handler = HFHandler()
        links = {"github": [], "huggingface": [], "other": []}
        
        handler._categorize_url("https://github.com/user/repo", links)
        
        assert len(links["github"]) == 1
        assert links["github"][0] == "https://github.com/user/repo"

    def test_categorize_huggingface_url(self):
        """Test categorizing HuggingFace URL"""
        handler = HFHandler()
        links = {"github": [], "huggingface": [], "other": []}
        
        handler._categorize_url("https://huggingface.co/user/model", links)
        
        assert len(links["huggingface"]) == 1
        assert links["huggingface"][0] == "https://huggingface.co/user/model"

    def test_categorize_other_url(self):
        """Test categorizing other URL"""
        handler = HFHandler()
        links = {"github": [], "huggingface": [], "other": []}
        
        handler._categorize_url("https://example.com/page", links)
        
        assert len(links["other"]) == 1
        assert links["other"][0] == "https://example.com/page"

    def test_categorize_github_false_positive(self):
        """Test filtering GitHub false positives"""
        handler = HFHandler()
        links = {"github": [], "huggingface": [], "other": []}
        
        handler._categorize_url("https://github.com/explore", links)
        
        assert len(links["github"]) == 0

    def test_categorize_huggingface_dataset(self):
        """Test filtering HuggingFace dataset URLs"""
        handler = HFHandler()
        links = {"github": [], "huggingface": [], "other": []}
        
        handler._categorize_url("https://huggingface.co/datasets/dataset", links)
        
        assert len(links["huggingface"]) == 0

    def test_categorize_duplicate_url(self):
        """Test handling duplicate URLs"""
        handler = HFHandler()
        links = {"github": [], "huggingface": [], "other": []}
        
        handler._categorize_url("https://github.com/user/repo", links)
        handler._categorize_url("https://github.com/user/repo", links)
        
        assert len(links["github"]) == 1


class TestHFHandlerExtractHyperlinks:
    """Test _extract_hyperlinks_from_text method"""

    def test_extract_empty_text(self):
        """Test extracting from empty text"""
        handler = HFHandler()
        result = handler._extract_hyperlinks_from_text("")
        
        assert result == {"github": [], "huggingface": [], "other": []}

    def test_extract_html_links(self):
        """Test extracting HTML links"""
        handler = HFHandler()
        text = '<a href="https://github.com/user/repo">Repository</a>'
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["github"]) == 1

    def test_extract_markdown_links(self):
        """Test extracting markdown links"""
        handler = HFHandler()
        text = "[Repository](https://github.com/user/repo)"
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["github"]) == 1

    def test_extract_plain_urls(self):
        """Test extracting plain URLs"""
        handler = HFHandler()
        text = "Check out https://github.com/user/repo for more info."
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["github"]) == 1

    def test_extract_context_aware_github(self):
        """Test context-aware GitHub URL extraction"""
        handler = HFHandler()
        text = "The repository is available on https://github.com/user/repo"
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["github"]) >= 1

    def test_extract_huggingface_links(self):
        """Test extracting HuggingFace links"""
        handler = HFHandler()
        text = "Based on https://huggingface.co/user/model"
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["huggingface"]) >= 1

    def test_extract_multiple_urls(self):
        """Test extracting multiple URLs"""
        handler = HFHandler()
        text = "See https://github.com/user/repo1 and https://github.com/user/repo2"
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["github"]) >= 2

    def test_extract_urls_with_fragments(self):
        """Test extracting URLs with fragments"""
        handler = HFHandler()
        text = "https://github.com/user/repo#section"
        result = handler._extract_hyperlinks_from_text(text)
        
        assert len(result["github"]) == 1
        assert "#" not in result["github"][0]


class TestHFHandlerGetJson:
    """Test _get_json method"""

    @patch("src.acmecli.hf_handler.urlopen")
    def test_get_json_success(self, mock_urlopen):
        """Test successful JSON retrieval"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"name": "test-model"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        handler = HFHandler()
        result = handler._get_json("https://huggingface.co/api/models/test")

        assert result == {"name": "test-model"}

    @patch("src.acmecli.hf_handler.urlopen")
    def test_get_json_http_error_401(self, mock_urlopen):
        """Test handling 401 HTTP error"""
        mock_error = HTTPError("https://huggingface.co/api/models/test", 401, "Unauthorized", {}, None)
        mock_urlopen.side_effect = mock_error

        handler = HFHandler()
        result = handler._get_json("https://huggingface.co/api/models/test")

        assert result == {}

    @patch("src.acmecli.hf_handler.urlopen")
    def test_get_json_http_error_other(self, mock_urlopen):
        """Test handling other HTTP errors"""
        mock_error = HTTPError("https://huggingface.co/api/models/test", 500, "Internal Server Error", {}, None)
        mock_urlopen.side_effect = mock_error

        handler = HFHandler()
        result = handler._get_json("https://huggingface.co/api/models/test")

        assert result == {}

    @patch("src.acmecli.hf_handler.urlopen")
    def test_get_json_url_error(self, mock_urlopen):
        """Test handling URL error"""
        mock_urlopen.side_effect = URLError("Network error")

        handler = HFHandler()
        result = handler._get_json("https://huggingface.co/api/models/test")

        assert result == {}

    @patch("src.acmecli.hf_handler.urlopen")
    def test_get_json_exception(self, mock_urlopen):
        """Test handling unexpected exception"""
        mock_urlopen.side_effect = Exception("Unexpected error")

        handler = HFHandler()
        result = handler._get_json("https://huggingface.co/api/models/test")

        assert result == {}


class TestHFHandlerFetchMeta:
    """Test fetch_meta method"""

    def test_fetch_meta_invalid_url(self):
        """Test fetching metadata with invalid URL"""
        handler = HFHandler()
        result = handler.fetch_meta("https://example.com/invalid")

        assert result == {}

    def test_fetch_meta_empty_path(self):
        """Test fetching metadata with empty path"""
        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/")

        assert result == {}

    def test_fetch_meta_dataset_url(self):
        """Test skipping dataset URLs"""
        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/datasets/test")

        assert result == {}

    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_empty_response(self, mock_get_json):
        """Test fetching metadata when API returns empty"""
        mock_get_json.return_value = {}

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/user/model")

        assert result == {}

    @patch("src.acmecli.hf_handler.urlopen")
    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_success(self, mock_get_json, mock_urlopen):
        """Test successful metadata fetching"""
        api_data = {
            "modelId": "user/model",
            "downloads": 1000,
            "likes": 100,
            "siblings": [{"rfilename": "model.safetensors"}],
            "cardData": {
                "readme": "# Model README\nSee https://github.com/user/repo"
            },
            "lastModified": "2024-01-01T00:00:00Z",
        }
        
        mock_get_json.return_value = api_data
        
        mock_html_response = MagicMock()
        mock_html_response.read.return_value = b'<html><a href="https://github.com/user/repo">Repo</a></html>'
        mock_html_response.__enter__.return_value = mock_html_response
        mock_urlopen.return_value = mock_html_response

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/user/model")

        assert result["modelId"] == "user/model"
        assert result["downloads"] == 1000
        assert "readme_text" in result
        assert "github" in result or "github_url" in result

    @patch("src.acmecli.hf_handler.urlopen")
    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_with_html_error(self, mock_get_json, mock_urlopen):
        """Test fetching metadata when HTML fetch fails"""
        api_data = {
            "modelId": "user/model",
            "downloads": 1000,
            "cardData": {"readme": "# README"},
        }
        
        mock_get_json.return_value = api_data
        mock_urlopen.side_effect = Exception("HTML fetch error")

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/user/model")

        assert result["modelId"] == "user/model"

    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_single_segment(self, mock_get_json):
        """Test fetching metadata with single segment model ID"""
        api_data = {"modelId": "gpt2", "downloads": 1000}
        mock_get_json.return_value = api_data

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/gpt2")

        assert result["modelId"] == "gpt2"

    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_with_blob_path(self, mock_get_json):
        """Test fetching metadata with blob in path"""
        api_data = {"modelId": "user/model", "downloads": 1000}
        mock_get_json.return_value = api_data

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/user/model/blob/main/README.md")

        assert result["modelId"] == "user/model"

    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_readme_variants(self, mock_get_json):
        """Test fetching metadata with different README field names"""
        api_data = {
            "modelId": "user/model",
            "cardData": {
                "---": "# README content",
            },
        }
        mock_get_json.return_value = api_data

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/user/model")

        assert "readme_text" in result

    @patch("src.acmecli.hf_handler.HFHandler._get_json")
    def test_fetch_meta_no_card_data(self, mock_get_json):
        """Test fetching metadata without cardData"""
        api_data = {
            "modelId": "user/model",
            "downloads": 1000,
        }
        mock_get_json.return_value = api_data

        handler = HFHandler()
        result = handler.fetch_meta("https://huggingface.co/user/model")

        assert result["readme_text"] == ""


class TestFetchHfMetadata:
    """Test module-level fetch_hf_metadata function"""

    @patch("src.acmecli.hf_handler.HFHandler")
    def test_fetch_hf_metadata(self, mock_handler_class):
        """Test module-level function"""
        mock_handler = MagicMock()
        mock_handler.fetch_meta.return_value = {"modelId": "test-model"}
        mock_handler_class.return_value = mock_handler

        result = fetch_hf_metadata("https://huggingface.co/user/model")

        assert result == {"modelId": "test-model"}
        mock_handler.fetch_meta.assert_called_once_with("https://huggingface.co/user/model")

