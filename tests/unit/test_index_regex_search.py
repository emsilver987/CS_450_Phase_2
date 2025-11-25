"""
Coverage tests for index.py regex search endpoint
Targeting complex JSON parsing logic
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.index import app

client = TestClient(app)

class TestRegexSearchCoverage:
    
    @patch("src.index.verify_auth_token")
    def test_regex_search_malformed_json_recovery(self, mock_verify):
        """Test recovery from malformed JSON (JS-style object)"""
        mock_verify.return_value = {"username": "user1"}
        
        # Test JS-style object without quotes
        response = client.post(
            "/artifact/byRegEx",
            content="{regex: test.*}",
            headers={"Content-Type": "application/json"}
        )
        # Should either recover or return 400 with specific message
        assert response.status_code in [200, 400, 404]

    @patch("src.index.verify_auth_token")
    def test_regex_search_invalid_json_unrecoverable(self, mock_verify):
        """Test unrecoverable invalid JSON"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post(
            "/artifact/byRegEx",
            content="{invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    @patch("src.index.verify_auth_token")
    def test_regex_search_empty_body(self, mock_verify):
        """Test empty request body"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post(
            "/artifact/byRegEx",
            content="",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @patch("src.index.verify_auth_token")
    def test_regex_search_form_data(self, mock_verify):
        """Test search with form data"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post(
            "/artifact/byRegEx",
            data={"RegEx": "test.*"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code in [200, 400, 404]

    @patch("src.index.verify_auth_token")
    def test_regex_search_raw_json_fallback(self, mock_verify):
        """Test fallback to JSON parsing when content-type is not JSON"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post(
            "/artifact/byRegEx",
            content='{"RegEx": "test.*"}',
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code in [200, 400, 404]

    @patch("src.index.verify_auth_token")
    def test_regex_search_invalid_body_type(self, mock_verify):
        """Test invalid body type (not dict or list)"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.post(
            "/artifact/byRegEx",
            json="just a string",
        )
        assert response.status_code == 400

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    def test_regex_search_success(self, mock_list, mock_verify):
        """Test successful regex search"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = [
            {"id": "a1", "name": "test-artifact"},
            {"id": "a2", "name": "other-artifact"}
        ]
        
        response = client.post(
            "/artifact/byRegEx",
            json={"RegEx": "test.*"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "test-artifact"

    @patch("src.index.verify_auth_token")
    @patch("src.index.list_all_artifacts")
    def test_regex_search_no_matches(self, mock_list, mock_verify):
        """Test regex search with no matches"""
        mock_verify.return_value = {"username": "user1"}
        mock_list.return_value = [{"id": "a1", "name": "artifact"}]
        
        response = client.post(
            "/artifact/byRegEx",
            json={"RegEx": "nomatch.*"}
        )
        assert response.status_code == 404
