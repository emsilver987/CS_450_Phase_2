"""
Unit tests for acmecli GitHub handler
"""
import os
import json
import base64
from unittest.mock import patch, MagicMock, Mock
from urllib.error import HTTPError, URLError
import pytest

from src.acmecli.github_handler import GitHubHandler, fetch_github_metadata


class TestGitHubHandlerInit:
    """Test GitHubHandler initialization"""

    def test_init_without_token(self):
        """Test initialization without GitHub token"""
        with patch.dict(os.environ, {}, clear=True):
            handler = GitHubHandler()
            assert handler._has_token is False
            assert "Authorization" not in handler._headers

    def test_init_with_ghp_token(self):
        """Test initialization with ghp_ token"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"}, clear=False):
            handler = GitHubHandler()
            assert handler._has_token is True
            assert handler._headers["Authorization"] == "Bearer ghp_test123"

    def test_init_with_github_pat_token(self):
        """Test initialization with github_pat_ token"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "github_pat_test123"}, clear=False):
            handler = GitHubHandler()
            assert handler._has_token is True
            assert handler._headers["Authorization"] == "Bearer github_pat_test123"

    def test_init_with_regular_token(self):
        """Test initialization with regular token"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token_123"}, clear=False):
            handler = GitHubHandler()
            assert handler._has_token is True
            assert handler._headers["Authorization"] == "token test_token_123"

    def test_init_with_placeholder_token(self):
        """Test initialization with placeholder token"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token_placeholder"}, clear=False):
            handler = GitHubHandler()
            assert handler._has_token is False
            assert "Authorization" not in handler._headers


class TestGitHubHandlerGetJson:
    """Test _get_json method"""

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_success(self, mock_urlopen):
        """Test successful JSON retrieval"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"name": "test-repo"}'
        mock_response.headers.get.return_value = "100"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        handler = GitHubHandler()
        result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {"name": "test-repo"}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_rate_limit_low(self, mock_urlopen):
        """Test handling low rate limit"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"name": "test-repo"}'
        mock_response.headers.get.side_effect = lambda key: "5" if key == "X-RateLimit-Remaining" else None
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        handler = GitHubHandler()
        result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {"name": "test-repo"}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_http_error_403(self, mock_urlopen):
        """Test handling 403 HTTP error"""
        mock_error = HTTPError("https://api.github.com/repos/test/repo", 403, "Forbidden", {}, None)
        mock_error.headers = {"X-RateLimit-Reset": "1234567890"}
        mock_urlopen.side_effect = mock_error

        handler = GitHubHandler()
        result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_http_error_401_with_token(self, mock_urlopen):
        """Test handling 401 HTTP error with token set"""
        mock_error = HTTPError("https://api.github.com/repos/test/repo", 401, "Unauthorized", {}, None)
        mock_urlopen.side_effect = mock_error

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"}, clear=False):
            handler = GitHubHandler()
            result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_http_error_401_without_token(self, mock_urlopen):
        """Test handling 401 HTTP error without token"""
        mock_error = HTTPError("https://api.github.com/repos/test/repo", 401, "Unauthorized", {}, None)
        mock_urlopen.side_effect = mock_error

        with patch.dict(os.environ, {}, clear=True):
            handler = GitHubHandler()
            result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_http_error_other(self, mock_urlopen):
        """Test handling other HTTP errors"""
        mock_error = HTTPError("https://api.github.com/repos/test/repo", 500, "Internal Server Error", {}, None)
        mock_urlopen.side_effect = mock_error

        handler = GitHubHandler()
        result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_url_error(self, mock_urlopen):
        """Test handling URL error"""
        mock_urlopen.side_effect = URLError("Network error")

        handler = GitHubHandler()
        result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {}

    @patch("src.acmecli.github_handler.urlopen")
    def test_get_json_exception(self, mock_urlopen):
        """Test handling unexpected exception"""
        mock_urlopen.side_effect = Exception("Unexpected error")

        handler = GitHubHandler()
        result = handler._get_json("https://api.github.com/repos/test/repo")

        assert result == {}


class TestGitHubHandlerFetchMeta:
    """Test fetch_meta method"""

    def test_fetch_meta_invalid_url(self):
        """Test fetching metadata with invalid URL"""
        handler = GitHubHandler()
        result = handler.fetch_meta("https://example.com/invalid")

        assert result == {}

    def test_fetch_meta_invalid_url_format(self):
        """Test fetching metadata with invalid URL format"""
        handler = GitHubHandler()
        result = handler.fetch_meta("not-a-url")

        assert result == {}

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_empty_repo_data(self, mock_get_json):
        """Test fetching metadata when repo data is empty"""
        mock_get_json.return_value = {}

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert result == {}

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_success(self, mock_get_json):
        """Test successful metadata fetching"""
        repo_data = {
            "name": "test-repo",
            "full_name": "test/test-repo",
            "description": "Test description",
            "stargazers_count": 100,
            "forks_count": 50,
            "watchers_count": 75,
            "size": 1024,
            "language": "Python",
            "topics": ["test", "example"],
            "license": {"spdx_id": "MIT"},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "pushed_at": "2024-01-03T00:00:00Z",
            "default_branch": "main",
            "open_issues_count": 5,
            "has_wiki": True,
            "has_pages": False,
            "archived": False,
            "disabled": False,
        }

        contributors_data = [
            {"login": "user1", "contributions": 10},
            {"login": "user2", "contributions": 5},
        ]

        contents_data = [
            {"type": "file", "path": "README.md"},
            {"type": "dir", "name": "src", "path": "src"},
        ]

        readme_data = {
            "content": base64.b64encode(b"# Test README").decode("utf-8")
        }

        prs_data = [
            {
                "number": 1,
                "state": "closed",
                "merged_at": "2024-01-01T00:00:00Z",
                "additions": 100,
            }
        ]

        reviews_data = [
            {"state": "APPROVED"},
            {"state": "COMMENTED"},
        ]

        files_data = [
            {"filename": "test.py", "additions": 50},
        ]

        commits_data = [
            {
                "sha": "abc123",
                "stats": {"additions": 200},
            }
        ]

        commit_detail_data = {
            "stats": {"additions": 200},
            "files": [{"filename": "test.py", "additions": 100}],
        }

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "contributors" in url:
                return contributors_data
            elif "contents" in url and "src" not in url:
                return contents_data
            elif "contents/src" in url:
                return [{"type": "file", "path": "src/main.py"}]
            elif "readme" in url:
                return readme_data
            elif "pulls" in url and "reviews" not in url and "files" not in url:
                return prs_data
            elif "reviews" in url:
                return reviews_data
            elif "files" in url and "pulls" in url:
                return files_data
            elif "commits" in url and "commits/abc123" not in url:
                return commits_data
            elif "commits/abc123" in url:
                return commit_detail_data
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert result["name"] == "test-repo"
        assert result["stars"] == 100
        assert result["contributors"]["user1"] == 10
        assert "readme_text" in result
        assert len(result["github"]["prs"]) > 0
        assert len(result["github"]["direct_commits"]) > 0

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_no_license(self, mock_get_json):
        """Test fetching metadata without license"""
        repo_data = {
            "name": "test-repo",
            "full_name": "test/test-repo",
        }
        mock_get_json.side_effect = lambda url: repo_data if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url else {}

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert result["license"] == ""

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_contributors_not_list(self, mock_get_json):
        """Test handling non-list contributors response"""
        repo_data = {"name": "test-repo"}
        mock_get_json.side_effect = lambda url: repo_data if "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url else {}

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert result["contributors"] == {}

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_readme_decode_error(self, mock_get_json):
        """Test handling README decode error"""
        repo_data = {"name": "test-repo"}
        readme_data = {"content": "invalid base64"}
        mock_get_json.side_effect = lambda url: (
            repo_data if "readme" not in url and "contributors" not in url and "contents" not in url and "pulls" not in url and "commits" not in url
            else readme_data if "readme" in url
            else {}
        )

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert result["readme_text"] == ""

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_prs_error(self, mock_get_json):
        """Test handling PR fetch error"""
        repo_data = {"name": "test-repo"}
        mock_get_json.side_effect = lambda url: (
            repo_data if "pulls" not in url and "commits" not in url and "contributors" not in url and "contents" not in url and "readme" not in url
            else Exception("PR error") if "pulls" in url
            else {}
        )

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert result["github"]["prs"] == []

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_commit_rate_limit(self, mock_get_json):
        """Test handling commit rate limit"""
        repo_data = {"name": "test-repo"}
        commits_data = [{"sha": "abc123", "stats": {"additions": 100}}]
        commit_error = HTTPError("url", 403, "Forbidden", {}, None)

        def get_json_side_effect(url):
            if "commits" in url and "commits/abc123" not in url:
                return commits_data
            elif "commits/abc123" in url:
                raise commit_error
            elif "pulls" not in url and "contributors" not in url and "contents" not in url and "readme" not in url:
                return repo_data
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert len(result["github"]["direct_commits"]) > 0


class TestGitHubHandlerFetchMetaAdvanced:
    """Test advanced fetch_meta scenarios for better coverage"""

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_contents_with_key_dirs(self, mock_get_json):
        """Test fetching contents with key directories"""
        repo_data = {"name": "test-repo"}
        contents_data = [
            {"type": "file", "path": "README.md"},
            {"type": "dir", "name": "src", "path": "src"},
            {"type": "dir", "name": "tests", "path": "tests"},
        ]
        src_contents = [{"type": "file", "path": "src/main.py"}]
        tests_contents = [{"type": "file", "path": "tests/test.py"}]

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "contents" in url and "src" not in url and "tests" not in url:
                return contents_data
            elif "contents/src" in url:
                return src_contents
            elif "contents/tests" in url:
                return tests_contents
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "repo_files" in result
        assert "README.md" in result["repo_files"]
        assert "src/main.py" in result["repo_files"]
        assert "tests/test.py" in result["repo_files"]

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_contents_exception(self, mock_get_json):
        """Test handling exception when fetching contents"""
        repo_data = {"name": "test-repo"}

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "contents" in url:
                raise Exception("Contents error")
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "repo_files" in result
        assert result["repo_files"] == set()

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_prs_with_reviews_and_files(self, mock_get_json):
        """Test fetching PRs with reviews and files"""
        repo_data = {"name": "test-repo"}
        prs_data = [
            {
                "number": 1,
                "state": "closed",
                "merged_at": "2024-01-01T00:00:00Z",
                "additions": 100,
            }
        ]
        reviews_data = [{"state": "APPROVED"}, {"state": "COMMENTED"}]
        files_data = [{"filename": "test.py", "additions": 50}]

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "pulls" in url and "reviews" not in url and "files" not in url:
                return prs_data
            elif "reviews" in url:
                return reviews_data
            elif "files" in url and "pulls" in url:
                return files_data
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert len(result["github"]["prs"]) > 0
        assert result["github"]["prs"][0]["approved"] is True
        assert result["github"]["prs"][0]["review_count"] == 2
        assert len(result["github"]["prs"][0]["files"]) > 0

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_prs_open_not_merged(self, mock_get_json):
        """Test fetching open PRs that are not merged"""
        repo_data = {"name": "test-repo"}
        prs_data = [
            {
                "number": 1,
                "state": "open",
                "merged_at": None,
                "additions": 50,
            }
        ]

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "pulls" in url:
                return prs_data
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert len(result["github"]["prs"]) > 0
        assert result["github"]["prs"][0]["merged"] is False

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_commits_with_stats(self, mock_get_json):
        """Test fetching commits with stats"""
        repo_data = {"name": "test-repo"}
        commits_data = [
            {
                "sha": "abc123",
                "stats": {"additions": 200},
            }
        ]
        commit_detail_data = {
            "stats": {"additions": 200},
            "files": [{"filename": "test.py", "additions": 100}],
        }

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "commits" in url and "commits/abc123" not in url:
                return commits_data
            elif "commits/abc123" in url:
                return commit_detail_data
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert len(result["github"]["direct_commits"]) > 0
        assert result["github"]["direct_commits"][0]["additions"] == 200

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_commits_other_http_error(self, mock_get_json):
        """Test handling other HTTP errors when fetching commit details"""
        repo_data = {"name": "test-repo"}
        commits_data = [{"sha": "abc123", "stats": {"additions": 100}}]
        commit_error = HTTPError("url", 500, "Internal Server Error", {}, None)

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "commits" in url and "commits/abc123" not in url:
                return commits_data
            elif "commits/abc123" in url:
                raise commit_error
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert len(result["github"]["direct_commits"]) > 0

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_commits_general_exception(self, mock_get_json):
        """Test handling general exception when fetching commit details"""
        repo_data = {"name": "test-repo"}
        commits_data = [{"sha": "abc123", "stats": {"additions": 100}}]

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "commits" in url and "commits/abc123" not in url:
                return commits_data
            elif "commits/abc123" in url:
                raise Exception("General error")
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert len(result["github"]["direct_commits"]) > 0

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_prs_exception(self, mock_get_json):
        """Test handling exception when fetching PRs"""
        repo_data = {"name": "test-repo"}

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "pulls" in url:
                raise Exception("PR error")
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result
        assert result["github"]["prs"] == []

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_readme_empty_content(self, mock_get_json):
        """Test handling README with empty content"""
        repo_data = {"name": "test-repo"}
        readme_data = {"content": ""}

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "readme" in url:
                return readme_data
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert result["readme_text"] == ""

    @patch("src.acmecli.github_handler.GitHubHandler._get_json")
    def test_fetch_meta_http_error_403_no_reset_header(self, mock_get_json):
        """Test handling 403 error without rate limit reset header"""
        repo_data = {"name": "test-repo"}
        mock_error = HTTPError("url", 403, "Forbidden", {}, None)
        mock_error.headers = {}  # No X-RateLimit-Reset header

        def get_json_side_effect(url):
            if "repos/test/repo" in url and "contributors" not in url and "contents" not in url and "readme" not in url and "pulls" not in url and "commits" not in url:
                return repo_data
            elif "pulls" in url:
                raise mock_error
            return {}

        mock_get_json.side_effect = get_json_side_effect

        handler = GitHubHandler()
        result = handler.fetch_meta("https://github.com/test/repo")

        assert "github" in result


class TestFetchGithubMetadata:
    """Test module-level fetch_github_metadata function"""

    @patch("src.acmecli.github_handler.GitHubHandler")
    def test_fetch_github_metadata(self, mock_handler_class):
        """Test module-level function"""
        mock_handler = MagicMock()
        mock_handler.fetch_meta.return_value = {"name": "test-repo"}
        mock_handler_class.return_value = mock_handler

        result = fetch_github_metadata("https://github.com/test/repo")

        assert result == {"name": "test-repo"}
        mock_handler.fetch_meta.assert_called_once_with("https://github.com/test/repo")

