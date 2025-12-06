"""
Unit tests for score_pull_requests metric
"""
import pytest
from unittest.mock import MagicMock


class TestScorePullRequests:
    """Test pull requests scoring"""

    def test_score_pull_requests_no_data(self):
        """Test scoring with no PR data"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {}
        result = score_pull_requests(context)
        assert result == 0.5

    def test_score_pull_requests_no_github(self):
        """Test scoring with no GitHub context"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {"other": "data"}
        result = score_pull_requests(context)
        assert result == 0.5

    def test_score_pull_requests_high_activity(self):
        """Test scoring with high merged PR activity"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": 100,
                "open_prs": 5
            }
        }
        result = score_pull_requests(context)
        assert result > 0.5
        assert 0.0 <= result <= 1.0

    def test_score_pull_requests_low_activity(self):
        """Test scoring with low merged PR activity"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": 2,
                "open_prs": 1
            }
        }
        result = score_pull_requests(context)
        assert 0.0 <= result <= 1.0

    def test_score_pull_requests_high_backlog(self):
        """Test scoring with high open PR backlog"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": 10,
                "open_prs": 100
            }
        }
        result = score_pull_requests(context)
        assert result < 0.5  # High backlog should lower score

    def test_score_pull_requests_balanced(self):
        """Test scoring with balanced PRs"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": 30,
                "open_prs": 10
            }
        }
        result = score_pull_requests(context)
        assert 0.0 <= result <= 1.0

    def test_score_pull_requests_using_total(self):
        """Test scoring using total_prs"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "total_prs": 50,
                "open_prs": 10
            }
        }
        result = score_pull_requests(context)
        assert 0.0 <= result <= 1.0

    def test_score_pull_requests_context_object(self):
        """Test scoring with context as object"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        class Context:
            def __init__(self):
                self.github = {"merged_prs": 20, "open_prs": 5}
        
        context = Context()
        result = score_pull_requests(context)
        assert 0.0 <= result <= 1.0

    def test_score_pull_requests_with_latency(self):
        """Test scoring with latency measurement"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests_with_latency
        
        context = {"github": {"merged_prs": 10, "open_prs": 5}}
        score, latency = score_pull_requests_with_latency(context)
        assert 0.0 <= score <= 1.0
        assert latency >= 0.0

    def test_score_pull_requests_invalid_data(self):
        """Test scoring with invalid PR data"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": "invalid",
                "open_prs": "invalid"
            }
        }
        result = score_pull_requests(context)
        assert result == 0.5  # Should return neutral on error

    def test_score_pull_requests_zero_values(self):
        """Test scoring with zero PR values"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": 0,
                "open_prs": 0
            }
        }
        result = score_pull_requests(context)
        # With 0 merged and 0 open: activity=0, backlog=1.0, score=0.6*0 + 0.4*1.0 = 0.4
        assert result == 0.4

    def test_score_pull_requests_max_values(self):
        """Test scoring with maximum PR values"""
        from src.acmecli.metrics.score_pull_requests import score_pull_requests
        
        context = {
            "github": {
                "merged_prs": 1000,
                "open_prs": 1000
            }
        }
        result = score_pull_requests(context)
        assert 0.0 <= result <= 1.0
        # Activity should be capped at 1.0, backlog at 0.0

    def test_extract_github_from_dict(self):
        """Test extracting GitHub from dict context"""
        from src.acmecli.metrics.score_pull_requests import _extract_github
        
        context = {"github": {"merged_prs": 10}}
        result = _extract_github(context)
        assert result == {"merged_prs": 10}

    def test_extract_github_from_object(self):
        """Test extracting GitHub from object context"""
        from src.acmecli.metrics.score_pull_requests import _extract_github
        
        class Context:
            def __init__(self):
                self.github = {"merged_prs": 10}
        
        context = Context()
        result = _extract_github(context)
        assert result == {"merged_prs": 10}

    def test_extract_github_missing(self):
        """Test extracting GitHub when missing"""
        from src.acmecli.metrics.score_pull_requests import _extract_github
        
        context = {}
        result = _extract_github(context)
        assert result == {}

