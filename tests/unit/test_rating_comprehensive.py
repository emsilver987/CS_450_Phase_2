"""
Comprehensive tests for src/services/rating.py
Targets scoring pipeline, metric integration, error handling
"""
import pytest
from unittest.mock import MagicMock, patch
from src.services.rating import (
    python_cmd, alias, analyze_model_content, run_acme_metrics,
    run_scorer, rate_model, RateRequest, create_metadata_from_files
)
from src.acmecli.types import MetricValue


# ============================================================================
# UTILITY FUNCTION TESTS
# ============================================================================

class TestUtilityFunctions:
    """Test utility helper functions"""
    
    def test_python_cmd(self):
        result = python_cmd()
        assert result in ["python", "python3"]
    
    def test_alias_first_key_exists(self):
        obj = {"name": "model1", "id": "m1"}
        assert alias(obj, "name", "title") == "model1"
    
    def test_alias_fallback_key(self):
        obj = {"title": "Model", "id": "m1"}
        assert alias(obj, "name", "title") == "Model"
    
    def test_alias_no_match(self):
        obj = {"id": "m1"}
        assert alias(obj, "name", "title") is None
    
    def test_alias_with_default(self):
        obj = {}
        # Testing behavior when neither key exists
        result = alias(obj, "missing1", "missing2")
        assert result is None


# ============================================================================
# METADATA CREATION TESTS
# ============================================================================

class TestMetadataCreation:
    """Test metadata extraction from files"""
    
    @patch("os.walk")
    @patch("builtins.open", create=True)
    def test_create_metadata_from_files(self, mock_open, mock_walk):
        mock_walk.return_value = [
            ("/model", [], ["README.md", "config.json", "model.bin"])
        ]
        
        mock_open.return_value.__enter__.return_value.read.return_value = "# Model README"
        
        result = create_metadata_from_files("/model")
        
        assert "repo_files" in result
        assert len(result["repo_files"]) > 0
    
    @patch("os.walk")
    def test_create_metadata_empty_directory(self, mock_walk):
        mock_walk.return_value = [("/empty", [], [])]
        
        result = create_metadata_from_files("/empty")
        
        assert "repo_files" in result
        assert len(result["repo_files"]) == 0


# ============================================================================
# ANALYZE MODEL CONTENT TESTS
# ============================================================================

class TestAnalyzeModelContent:
    """Test model content analysis"""
    
    @patch("src.services.rating.list_models")
    @patch("src.services.rating.download_model")
    @patch("src.services.rating.create_metadata_from_files")
    @patch("src.services.rating.run_acme_metrics")
    def test_analyze_from_s3(self, mock_metrics, mock_create, mock_download, mock_list):
        mock_list.return_value = {"models": [{"name": "model1", "version": "1.0.0"}]}
        mock_download.return_value = b"zip content"
        mock_create.return_value = {"repo_files": {"README.md"}}
        mock_metrics.return_value = {"net_score": 0.85}
        
        result = analyze_model_content("model1")
        
        assert "net_score" in result
        assert result["net_score"] == 0.85
    
    @patch("src.services.rating.list_models")
    @patch("src.services.rating.download_from_huggingface")
    @patch("src.services.rating.create_metadata_from_files")
    @patch("src.services.rating.run_acme_metrics")
    def test_analyze_from_huggingface(self, mock_metrics, mock_create, mock_hf, mock_list):
        mock_list.return_value = {"models": []}  # Not in S3
        mock_hf.return_value = b"zip content"
        mock_create.return_value = {"repo_files": {"README.md"}}
        mock_metrics.return_value = {"net_score": 0.75}
        
        result = analyze_model_content("https://huggingface.co/user/model")
        
        assert "net_score" in result
        assert result["net_score"] == 0.75


# ============================================================================
# ACME METRICS INTEGRATION TESTS
# ============================================================================

class TestACMEMetrics:
    """Test ACME metrics integration"""
    
    def test_run_acme_metrics_with_metric_value(self):
        metadata = {"repo_files": set()}
        metrics = {
            "bus_factor": lambda m: MetricValue("bus_factor", 0.8, 100),
            "license": lambda m: MetricValue("license", 1.0, 50)
        }
        
        result = run_acme_metrics(metadata, metrics)
        
        assert "net_score" in result
        assert result["bus_factor"] == 0.8
        assert result["license"] == 1.0
    
    def test_run_acme_metrics_with_raw_scores(self):
        metadata = {"repo_files": set()}
        metrics = {
            "ramp_up": lambda m: 0.7,
            "correctness": lambda m: 0.9
        }
        
        result = run_acme_metrics(metadata, metrics)
        
        assert result["ramp_up"] == 0.7
        assert result["correctness"] == 0.9
    
    def test_run_acme_metrics_mixed_types(self):
        metadata = {"repo_files": set()}
        metrics = {
            "metric1": lambda m: MetricValue("metric1", 0.6, 10),
            "metric2": lambda m: 0.8,
            "metric3": lambda m: MetricValue("metric3", 0.9, 20)
        }
        
        result = run_acme_metrics(metadata, metrics)
        
        assert "net_score" in result
        assert result["metric1"] == 0.6
        assert result["metric2"] == 0.8
        assert result["metric3"] == 0.9
    
    def test_run_acme_metrics_calculates_net_score(self):
        metadata = {"repo_files": set()}
        metrics = {
            "m1": lambda m: 1.0,
            "m2": lambda m: 0.8,
            "m3": lambda m: 0.6
        }
        
        result = run_acme_metrics(metadata, metrics)
        
        # Should calculate net score from individual metrics
        assert "net_score" in result
        assert 0 <= result["net_score"] <= 1


# ============================================================================
# RUN SCORER TESTS
# ============================================================================

class TestRunScorer:
    """Test the main scoring runner"""
    
    @patch("subprocess.run")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"})
    def test_run_scorer_with_subprocess(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"net_score": 0.9, "license": 1.0}'
        
        result = run_scorer("https://github.com/user/repo")
        
        assert result["net_score"] == 0.9
        assert result["license"] == 1.0
        assert mock_run.called
    
    @patch("subprocess.run")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"})
    def test_run_scorer_subprocess_error(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = "Error occurred"
        
        result = run_scorer("https://github.com/user/repo")
        
        # Should handle error gracefully
        assert isinstance(result, dict)
    
    @patch("src.services.rating.analyze_model_content")
    @patch.dict("os.environ", {}, clear=True)  # No GITHUB_TOKEN
    def test_run_scorer_without_github_token(self, mock_analyze):
        mock_analyze.return_value = {"net_score": 0.85}
        
        result = run_scorer("model1")
        
        # Should use analyze_model_content instead
        assert result["net_score"] == 0.85


# ============================================================================
# RATE MODEL ENDPOINT TESTS
# ============================================================================

class TestRateModel:
    """Test the rate_model endpoint function"""
    
    @patch("src.services.rating.run_scorer")
    def test_rate_model_success(self, mock_scorer):
        mock_scorer.return_value = {
            "net_score": 0.85,
            "bus_factor": 0.8,
            "license": 1.0,
            "ramp_up": 0.75
        }
        
        body = RateRequest(target="model1")
        result = rate_model("model1", body)
        
        assert "data" in result
        assert result["data"]["netScore"] == 0.85
    
    @patch("src.services.rating.run_scorer")
    def test_rate_model_with_subscores(self, mock_scorer):
        mock_scorer.return_value = {
            "net_score": 0.8,
            "bus_factor": 0.7,
            "correctness": 0.9,
            "ramp_up": 0.75,
            "responsive_maintainer": 0.85,
            "license": 1.0
        }
        
        body = RateRequest(target="model1")
        result = rate_model("model1", body)
        
        assert "subscores" in result["data"]
        subscores = result["data"]["subscores"]
        assert subscores["BusFactor"] == 0.7
        assert subscores["Correctness"] == 0.9
    
    @patch("src.services.rating.run_scorer")
    def test_rate_model_enforce_threshold_pass(self, mock_scorer):
        mock_scorer.return_value = {
            "net_score": 0.85,
            "license": 1.0
        }
        
        body = RateRequest(target="model1")
        result = rate_model("model1", body, enforce=True)
        
        # Should pass with high scores
        assert result["data"]["netScore"] == 0.85
    
    @patch("src.services.rating.run_scorer")
    def test_rate_model_enforce_threshold_fail(self, mock_scorer):
        from fastapi import HTTPException
        
        mock_scorer.return_value = {
            "net_score": 0.4,  # Below 0.5 threshold
            "license": 0.5
        }
        
        body = RateRequest(target="model1")
        
        with pytest.raises(HTTPException) as exc:
            rate_model("model1", body, enforce=True)
        
        assert exc.value.status_code == 422
    
    @patch("src.services.rating.run_scorer")
    def test_rate_model_enforce_license_fail(self, mock_scorer):
        from fastapi import HTTPException
        
        mock_scorer.return_value = {
            "net_score": 0.8,
            "license": 0.4  # Below 0.5 threshold
        }
        
        body = RateRequest(target="model1")
        
        with pytest.raises(HTTPException) as exc:
            rate_model("model1", body, enforce=True)
        
        assert exc.value.status_code == 422


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in rating service"""
    
    @patch("src.services.rating.list_models")
    def test_analyze_model_not_found(self, mock_list):
        mock_list.return_value = {"models": []}
        
        # Should handle model not found
        with patch("src.services.rating.download_from_huggingface") as mock_hf:
            mock_hf.side_effect = Exception("Not found")
            
            with pytest.raises(Exception):
                analyze_model_content("nonexistent/model")
    
    @patch("subprocess.run")
    def test_run_scorer_json_parse_error(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "invalid json"
        
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test"}):
            result = run_scorer("https://github.com/user/repo")
            
            # Should handle JSON parse error
            assert isinstance(result, dict)
    
    @patch("src.services.rating.run_scorer")
    def test_rate_model_scorer_failure(self, mock_scorer):
        mock_scorer.side_effect = Exception("Scoring failed")
        
        body = RateRequest(target="model1")
        
        with pytest.raises(Exception):
            rate_model("model1", body)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test end-to-end rating flow"""
    
    @patch("src.services.rating.list_models")
    @patch("src.services.rating.download_model")
    @patch("src.services.rating.create_metadata_from_files")
    @patch("src.services.rating.METRIC_FUNCTIONS")
    def test_full_rating_pipeline(self, mock_metrics_funcs, mock_create, mock_download, mock_list):
        # Setup full pipeline
        mock_list.return_value = {"models": [{"name": "model1", "version": "1.0.0"}]}
        mock_download.return_value = b"zip content"
        mock_create.return_value = {"repo_files": {"README.md"}, "readme": "Test"}
        
        # Mock metrics
        mock_metrics_funcs = {
            "bus_factor": lambda m: MetricValue("bus_factor", 0.8, 10),
            "license": lambda m: 1.0
        }
        
        with patch("src.services.rating.run_acme_metrics") as mock_run_metrics:
            mock_run_metrics.return_value = {"net_score": 0.85}
            
            result = analyze_model_content("model1")
            
            assert "net_score" in result
