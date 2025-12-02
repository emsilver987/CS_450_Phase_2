"""
Unit tests for acmecli CLI module
"""
import os
import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import pytest

from src.acmecli.cli import (
    setup_logging,
    classify,
    extract_urls,
    process_url,
    main,
)


class TestSetupLogging:
    """Test setup_logging function"""

    def test_setup_logging_default(self):
        """Test logging setup with default settings"""
        with patch.dict(os.environ, {}, clear=True):
            setup_logging()
            root_logger = logging.getLogger()
            assert len(root_logger.handlers) > 0
            assert isinstance(root_logger.handlers[0], logging.StreamHandler)

    def test_setup_logging_with_log_file(self, tmp_path):
        """Test logging setup with log file"""
        log_file = tmp_path / "test.log"
        with patch.dict(os.environ, {"LOG_FILE": str(log_file)}, clear=False):
            setup_logging()
            root_logger = logging.getLogger()
            assert len(root_logger.handlers) > 0
            assert isinstance(root_logger.handlers[0], logging.FileHandler)
            assert log_file.exists()

    def test_setup_logging_level_0(self):
        """Test logging setup with level 0 (CRITICAL+1)"""
        with patch.dict(os.environ, {"LOG_LEVEL": "0"}, clear=False):
            setup_logging()
            root_logger = logging.getLogger()
            handler = root_logger.handlers[0]
            assert handler.level > logging.CRITICAL

    def test_setup_logging_level_1(self):
        """Test logging setup with level 1 (INFO)"""
        with patch.dict(os.environ, {"LOG_LEVEL": "1"}, clear=False):
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_level_2(self):
        """Test logging setup with level 2 (DEBUG)"""
        with patch.dict(os.environ, {"LOG_LEVEL": "2"}, clear=False):
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG

    def test_setup_logging_invalid_level(self):
        """Test logging setup with invalid level defaults to ERROR"""
        with patch.dict(os.environ, {"LOG_LEVEL": "invalid"}, clear=False):
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.ERROR


class TestClassify:
    """Test classify function"""

    def test_classify_dataset_url(self):
        """Test classifying HuggingFace dataset URL"""
        url = "https://huggingface.co/datasets/squad"
        assert classify(url) == "DATASET"

    def test_classify_github_url(self):
        """Test classifying GitHub URL"""
        url = "https://github.com/user/repo"
        assert classify(url) == "MODEL_GITHUB"

    def test_classify_huggingface_model_url(self):
        """Test classifying HuggingFace model URL"""
        url = "https://huggingface.co/user/model"
        assert classify(url) == "MODEL_HF"

    def test_classify_other_url(self):
        """Test classifying other URL"""
        url = "https://example.com/code"
        assert classify(url) == "CODE"

    def test_classify_url_with_whitespace(self):
        """Test classifying URL with whitespace"""
        url = "  https://github.com/user/repo  "
        assert classify(url) == "MODEL_GITHUB"

    def test_classify_lowercase_url(self):
        """Test classifying lowercase URL"""
        url = "HTTPS://GITHUB.COM/USER/REPO"
        assert classify(url) == "MODEL_GITHUB"


class TestExtractUrls:
    """Test extract_urls function"""

    def test_extract_urls_single(self):
        """Test extracting single URL"""
        raw = "https://github.com/user/repo"
        urls = extract_urls(raw)
        assert urls == ["https://github.com/user/repo"]

    def test_extract_urls_multiple(self):
        """Test extracting multiple URLs"""
        raw = "https://github.com/user/repo1,https://github.com/user/repo2"
        urls = extract_urls(raw)
        assert len(urls) == 2
        assert urls[0] == "https://github.com/user/repo1"
        assert urls[1] == "https://github.com/user/repo2"

    def test_extract_urls_with_whitespace(self):
        """Test extracting URLs with whitespace"""
        raw = "  https://github.com/user/repo1  ,  https://github.com/user/repo2  "
        urls = extract_urls(raw)
        assert len(urls) == 2
        assert urls[0] == "https://github.com/user/repo1"
        assert urls[1] == "https://github.com/user/repo2"

    def test_extract_urls_empty(self):
        """Test extracting URLs from empty string"""
        raw = ""
        urls = extract_urls(raw)
        assert urls == []

    def test_extract_urls_none(self):
        """Test extracting URLs from None"""
        raw = None
        urls = extract_urls(raw)
        assert urls == []

    def test_extract_urls_empty_after_split(self):
        """Test extracting URLs with empty entries"""
        raw = "https://github.com/user/repo1,,https://github.com/user/repo2"
        urls = extract_urls(raw)
        assert len(urls) == 2


class TestProcessUrl:
    """Test process_url function"""

    @patch("src.acmecli.cli.REGISTRY", [])
    @patch("src.acmecli.cli.compute_net_score")
    def test_process_url_github(self, mock_compute_net_score, mock_registry):
        """Test processing GitHub URL"""
        mock_compute_net_score.return_value = (0.5, 100)
        mock_github_handler = MagicMock()
        mock_github_handler.fetch_meta.return_value = {
            "name": "test-repo",
            "stars": 100,
        }
        mock_hf_handler = MagicMock()
        mock_cache = MagicMock()

        result = process_url(
            "https://github.com/user/repo",
            mock_github_handler,
            mock_hf_handler,
            mock_cache,
        )

        assert result is not None
        assert result.name == "repo"
        assert result.category == "MODEL"
        mock_github_handler.fetch_meta.assert_called_once()

    @patch("src.acmecli.cli.REGISTRY", [])
    @patch("src.acmecli.cli.compute_net_score")
    def test_process_url_huggingface(self, mock_compute_net_score, mock_registry):
        """Test processing HuggingFace URL"""
        mock_compute_net_score.return_value = (0.5, 100)
        mock_github_handler = MagicMock()
        mock_hf_handler = MagicMock()
        mock_hf_handler.fetch_meta.return_value = {
            "name": "test-model",
            "downloads": 1000,
        }
        mock_cache = MagicMock()

        result = process_url(
            "https://huggingface.co/user/model",
            mock_github_handler,
            mock_hf_handler,
            mock_cache,
        )

        assert result is not None
        assert result.name == "model"
        assert result.category == "MODEL"
        mock_hf_handler.fetch_meta.assert_called_once()

    @patch("src.acmecli.cli.REGISTRY", [])
    def test_process_url_unsupported(self, mock_registry):
        """Test processing unsupported URL type"""
        mock_github_handler = MagicMock()
        mock_hf_handler = MagicMock()
        mock_cache = MagicMock()

        result = process_url(
            "https://example.com/code",
            mock_github_handler,
            mock_hf_handler,
            mock_cache,
        )

        assert result is None

    @patch("src.acmecli.cli.REGISTRY", [])
    @patch("src.acmecli.cli.compute_net_score")
    def test_process_url_no_meta(self, mock_compute_net_score, mock_registry):
        """Test processing URL when handler returns None"""
        mock_github_handler = MagicMock()
        mock_github_handler.fetch_meta.return_value = None
        mock_hf_handler = MagicMock()
        mock_cache = MagicMock()

        result = process_url(
            "https://github.com/user/repo",
            mock_github_handler,
            mock_hf_handler,
            mock_cache,
        )

        assert result is None

    @patch("src.acmecli.cli.REGISTRY", [])
    @patch("src.acmecli.cli.compute_net_score")
    def test_process_url_metric_error(self, mock_compute_net_score, mock_registry):
        """Test processing URL when metric computation fails"""
        mock_compute_net_score.return_value = (0.5, 100)
        mock_metric = MagicMock()
        mock_metric.name = "test_metric"
        mock_metric.score.side_effect = Exception("Metric error")
        mock_registry.__iter__.return_value = [mock_metric]

        mock_github_handler = MagicMock()
        mock_github_handler.fetch_meta.return_value = {"name": "test-repo"}
        mock_hf_handler = MagicMock()
        mock_cache = MagicMock()

        result = process_url(
            "https://github.com/user/repo",
            mock_github_handler,
            mock_hf_handler,
            mock_cache,
        )

        assert result is not None


class TestMain:
    """Test main function"""

    @patch("src.acmecli.cli.setup_logging")
    @patch("src.acmecli.cli.Path")
    @patch("src.acmecli.cli.GitHubHandler")
    @patch("src.acmecli.cli.HFHandler")
    @patch("src.acmecli.cli.InMemoryCache")
    @patch("src.acmecli.cli.process_url")
    @patch("src.acmecli.cli.write_ndjson")
    def test_main_success(
        self,
        mock_write_ndjson,
        mock_process_url,
        mock_cache_class,
        mock_hf_handler_class,
        mock_github_handler_class,
        mock_path_class,
        mock_setup_logging,
    ):
        """Test main function with successful processing"""
        mock_path = MagicMock()
        mock_path.read_text.return_value = "https://github.com/user/repo\n"
        mock_path_class.return_value = mock_path

        mock_row = MagicMock()
        mock_row.name = "repo"
        mock_process_url.return_value = mock_row

        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache
        mock_github_handler = MagicMock()
        mock_github_handler_class.return_value = mock_github_handler
        mock_hf_handler = MagicMock()
        mock_hf_handler_class.return_value = mock_hf_handler

        result = main(["cli.py", "urls.txt"])

        assert result == 0
        mock_setup_logging.assert_called_once()
        mock_process_url.assert_called_once()
        mock_write_ndjson.assert_called_once()

    @patch("src.acmecli.cli.setup_logging")
    def test_main_insufficient_args(self, mock_setup_logging):
        """Test main function with insufficient arguments"""
        result = main(["cli.py"])
        assert result == 1

    @patch("src.acmecli.cli.setup_logging")
    @patch("src.acmecli.cli.Path")
    @patch("src.acmecli.cli.GitHubHandler")
    @patch("src.acmecli.cli.HFHandler")
    @patch("src.acmecli.cli.InMemoryCache")
    @patch("src.acmecli.cli.process_url")
    @patch("src.acmecli.cli.write_ndjson")
    def test_main_skip_unsupported_urls(
        self,
        mock_write_ndjson,
        mock_process_url,
        mock_cache_class,
        mock_hf_handler_class,
        mock_github_handler_class,
        mock_path_class,
        mock_setup_logging,
    ):
        """Test main function skips unsupported URL types"""
        mock_path = MagicMock()
        mock_path.read_text.return_value = "https://example.com/code\n"
        mock_path_class.return_value = mock_path

        mock_process_url.return_value = None

        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache
        mock_github_handler = MagicMock()
        mock_github_handler_class.return_value = mock_github_handler
        mock_hf_handler = MagicMock()
        mock_hf_handler_class.return_value = mock_hf_handler

        result = main(["cli.py", "urls.txt"])

        assert result == 0
        mock_write_ndjson.assert_not_called()

    @patch("src.acmecli.cli.setup_logging")
    @patch("src.acmecli.cli.Path")
    @patch("src.acmecli.cli.GitHubHandler")
    @patch("src.acmecli.cli.HFHandler")
    @patch("src.acmecli.cli.InMemoryCache")
    @patch("src.acmecli.cli.process_url")
    @patch("src.acmecli.cli.write_ndjson")
    def test_main_empty_file(
        self,
        mock_write_ndjson,
        mock_process_url,
        mock_cache_class,
        mock_hf_handler_class,
        mock_github_handler_class,
        mock_path_class,
        mock_setup_logging,
    ):
        """Test main function with empty file"""
        mock_path = MagicMock()
        mock_path.read_text.return_value = ""
        mock_path_class.return_value = mock_path

        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache
        mock_github_handler = MagicMock()
        mock_github_handler_class.return_value = mock_github_handler
        mock_hf_handler = MagicMock()
        mock_hf_handler_class.return_value = mock_hf_handler

        result = main(["cli.py", "urls.txt"])

        assert result == 0
        mock_process_url.assert_not_called()
        mock_write_ndjson.assert_not_called()

