"""
Unit tests for LLM service.
Tests the LLM service functions with mocked API calls.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services import llm_service


class TestLLMService:
    """Test suite for LLM service functions."""

    def test_is_llm_available_with_key(self):
        """Test is_llm_available returns True when API key is set."""
        with patch.dict(os.environ, {"GEN_AI_STUDIO_API_KEY": "test-key"}):
            # Reload module to pick up new env var
            import importlib
            importlib.reload(llm_service)
            assert llm_service.is_llm_available() is True

    def test_is_llm_available_without_key(self):
        """Test is_llm_available returns False when API key is not set."""
        with patch.dict(os.environ, {"GEN_AI_STUDIO_API_KEY": ""}, clear=True):
            import importlib
            importlib.reload(llm_service)
            assert llm_service.is_llm_available() is False

    @patch('src.services.llm_service._call_llm_api')
    def test_analyze_license_compatibility_success(self, mock_call_api):
        """Test license compatibility analysis with successful API response."""
        mock_response = {
            "compatible": True,
            "reason": "Both licenses are permissive",
            "restrictions": []
        }
        mock_call_api.return_value = json.dumps(mock_response)
        
        result = llm_service.analyze_license_compatibility(
            model_license_text="MIT License",
            github_license_text="Apache License 2.0",
            use_case="fine-tune+inference"
        )
        
        assert result is not None
        assert result["compatible"] is True
        assert "reason" in result
        mock_call_api.assert_called_once()

    @patch('src.services.llm_service._call_llm_api')
    def test_analyze_license_compatibility_json_in_markdown(self, mock_call_api):
        """Test license compatibility handles JSON wrapped in markdown code blocks."""
        mock_response = "```json\n{\"compatible\": false, \"reason\": \"Incompatible\"}\n```"
        mock_call_api.return_value = mock_response
        
        result = llm_service.analyze_license_compatibility(
            model_license_text="GPL-3.0",
            github_license_text="MIT",
            use_case="fine-tune+inference"
        )
        
        assert result is not None
        assert result["compatible"] is False

    @patch('src.services.llm_service._call_llm_api')
    def test_analyze_license_compatibility_api_failure(self, mock_call_api):
        """Test license compatibility returns None when API fails."""
        mock_call_api.return_value = None
        
        result = llm_service.analyze_license_compatibility(
            model_license_text="MIT License",
            github_license_text="Apache License 2.0",
            use_case="fine-tune+inference"
        )
        
        assert result is None

    @patch('src.services.llm_service._call_llm_api')
    def test_extract_model_card_keywords_success(self, mock_call_api):
        """Test keyword extraction with successful API response."""
        mock_response = '["transformer", "NLP", "BERT", "text classification"]'
        mock_call_api.return_value = mock_response
        
        keywords = llm_service.extract_model_card_keywords(
            "BERT model for NLP tasks"
        )
        
        assert keywords is not None
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert "transformer" in keywords or "NLP" in keywords

    @patch('src.services.llm_service._call_llm_api')
    def test_extract_model_card_keywords_json_in_markdown(self, mock_call_api):
        """Test keyword extraction handles JSON wrapped in markdown."""
        mock_response = '```json\n["keyword1", "keyword2"]\n```'
        mock_call_api.return_value = mock_response
        
        keywords = llm_service.extract_model_card_keywords("Test model card")
        
        assert keywords is not None
        assert isinstance(keywords, list)
        assert len(keywords) == 2

    @patch('src.services.llm_service._call_llm_api')
    def test_extract_model_card_keywords_api_failure(self, mock_call_api):
        """Test keyword extraction returns None when API fails."""
        mock_call_api.return_value = None
        
        keywords = llm_service.extract_model_card_keywords("Test model card")
        
        assert keywords is None

    @patch('src.services.llm_service._call_llm_api')
    def test_generate_helpful_error_message_success(self, mock_call_api):
        """Test error message generation with successful API response."""
        mock_response = "A helpful error message explaining what went wrong."
        mock_call_api.return_value = mock_response
        
        message = llm_service.generate_helpful_error_message(
            error_type="INGESTIBILITY_FAILURE",
            error_context={"modelId": "test-model"},
            user_action="Rating model"
        )
        
        assert message is not None
        assert isinstance(message, str)
        assert len(message) > 0

    @patch('src.services.llm_service._call_llm_api')
    def test_generate_helpful_error_message_api_failure(self, mock_call_api):
        """Test error message generation returns None when API fails."""
        mock_call_api.return_value = None
        
        message = llm_service.generate_helpful_error_message(
            error_type="INGESTIBILITY_FAILURE",
            error_context={"modelId": "test-model"},
            user_action="Rating model"
        )
        
        assert message is None

    @patch('src.services.llm_service._call_llm_api')
    def test_analyze_lineage_config_success(self, mock_call_api):
        """Test lineage config analysis with successful API response."""
        mock_response = {
            "parent_models": ["bert-base-uncased"],
            "base_architecture": "bert",
            "lineage_notes": "Fine-tuned from BERT"
        }
        mock_call_api.return_value = json.dumps(mock_response)
        
        config = {"_name_or_path": "bert-base-uncased", "model_type": "bert"}
        result = llm_service.analyze_lineage_config(config)
        
        assert result is not None
        assert "parent_models" in result
        assert isinstance(result["parent_models"], list)

    @patch('src.services.llm_service._call_llm_api')
    def test_analyze_lineage_config_api_failure(self, mock_call_api):
        """Test lineage config analysis returns None when API fails."""
        mock_call_api.return_value = None
        
        config = {"_name_or_path": "bert-base-uncased"}
        result = llm_service.analyze_lineage_config(config)
        
        assert result is None

    @patch('src.services.llm_service.requests.post')
    @patch('src.services.llm_service.PURDUE_GENAI_API_KEY', 'test-key')
    @patch('src.services.llm_service.time.time')
    @patch('src.services.llm_service.time.sleep')
    def test_call_llm_api_success(self, mock_sleep, mock_time, mock_post):
        """Test successful LLM API call."""
        mock_time.return_value = 0.0
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        result = llm_service._call_llm_api("Test prompt", "System message")
        
        assert result == "Test response"
        mock_post.assert_called_once()
        assert "Authorization" in mock_post.call_args[1]["headers"]

    @patch('src.services.llm_service.requests.post')
    @patch('src.services.llm_service.PURDUE_GENAI_API_KEY', None)
    def test_call_llm_api_no_key(self, mock_post):
        """Test LLM API call returns None when API key is not set."""
        result = llm_service._call_llm_api("Test prompt")
        
        assert result is None
        mock_post.assert_not_called()

    @patch('src.services.llm_service.requests.post')
    @patch('src.services.llm_service.PURDUE_GENAI_API_KEY', 'test-key')
    @patch('src.services.llm_service.time.time')
    @patch('src.services.llm_service.time.sleep')
    def test_call_llm_api_request_exception(self, mock_sleep, mock_time, mock_post):
        """Test LLM API call handles request exceptions gracefully."""
        mock_time.return_value = 0.0
        mock_post.side_effect = Exception("Network error")
        
        result = llm_service._call_llm_api("Test prompt")
        
        assert result is None

    @patch('src.services.llm_service.time.time')
    @patch('src.services.llm_service.time.sleep')
    def test_rate_limit(self, mock_sleep, mock_time):
        """Test rate limiting between requests."""
        # Reset the global state
        llm_service._last_request_time = 0.0
        
        # First call at 0.0 - since _last_request_time is 0.0, time_since_last is 0.0 < 1.0, so sleeps
        mock_time.return_value = 0.0
        llm_service._rate_limit()
        assert mock_sleep.call_count == 1  # First call sleeps because initial state is 0.0
        
        # Second call at 0.5 - since _last_request_time was updated to 0.0, time_since_last is 0.5 < 1.0, so sleeps
        mock_time.return_value = 0.5
        llm_service._rate_limit()
        assert mock_sleep.call_count == 2
        # Should sleep for 1.0 - 0.5 = 0.5 seconds
        assert abs(mock_sleep.call_args[0][0] - 0.5) < 0.01
        
        # Third call at 2.0 - since _last_request_time is 0.5, time_since_last is 1.5 > 1.0, so no sleep
        mock_time.return_value = 2.0
        llm_service._rate_limit()
        assert mock_sleep.call_count == 2  # No additional sleep

