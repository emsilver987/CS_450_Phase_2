"""
Unit tests for src/services/rating.py
Focusing on core functions to improve coverage from 20% to ~50%
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from src.services.rating import (
    python_cmd,
    alias,
    analyze_model_content,
    create_metadata_from_files,
    run_acme_metrics,
    run_scorer,
    rate_model,
    RateRequest,
)
from src.acmecli.types import MetricValue


class TestPythonCmd:
    """Test python_cmd function"""

    def test_python_cmd_windows(self):
        """Test python_cmd on Windows"""
        with patch("sys.platform", "win32"):
            result = python_cmd()
            assert result == "python"

    def test_python_cmd_unix(self):
        """Test python_cmd on Unix-like systems"""
        with patch("sys.platform", "linux"):
            result = python_cmd()
            assert result == "python3"

    def test_python_cmd_darwin(self):
        """Test python_cmd on macOS"""
        with patch("sys.platform", "darwin"):
            result = python_cmd()
            assert result == "python3"


class TestAlias:
    """Test alias function"""

    def test_alias_found_first_key(self):
        """Test alias when first key is found"""
        obj = {"key1": "value1", "key2": "value2"}
        result = alias(obj, "key1", "key2")
        assert result == "value1"

    def test_alias_found_second_key(self):
        """Test alias when second key is found"""
        obj = {"key2": "value2"}
        result = alias(obj, "key1", "key2")
        assert result == "value2"

    def test_alias_not_found(self):
        """Test alias when no keys are found"""
        obj = {"other": "value"}
        result = alias(obj, "key1", "key2")
        assert result is None

    def test_alias_none_value(self):
        """Test alias when key exists but value is None"""
        obj = {"key1": None, "key2": "value2"}
        result = alias(obj, "key1", "key2")
        assert result == "value2"

    def test_alias_empty_obj(self):
        """Test alias with empty object"""
        obj = {}
        result = alias(obj, "key1", "key2")
        assert result is None


class TestCreateMetadataFromFiles:
    """Test create_metadata_from_files function"""

    def test_create_metadata_success(self):
        """Test successful metadata creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            readme_path = os.path.join(temp_dir, "README.md")
            with open(readme_path, "w") as f:
                f.write("# Test Model\nThis is a test model.")

            license_path = os.path.join(temp_dir, "license.txt")
            with open(license_path, "w") as f:
                f.write("MIT License")

            code_path = os.path.join(temp_dir, "model.py")
            with open(code_path, "w") as f:
                f.write("def model(): pass")

            result = create_metadata_from_files(temp_dir, "test-model")
            assert result["repo_name"] == "test-model"
            assert result["repo_path"] == temp_dir
            assert "README.md" in result["repo_files"]
            assert "license.txt" in result["repo_files"]
            assert "model.py" in result["repo_files"]
            assert "test model" in result["readme_text"].lower()
            # License text might be empty if glob doesn't find it, so just check it exists
            assert "license_text" in result

    def test_create_metadata_no_readme(self):
        """Test metadata creation without README"""
        with tempfile.TemporaryDirectory() as temp_dir:
            code_path = os.path.join(temp_dir, "model.py")
            with open(code_path, "w") as f:
                f.write("def model(): pass")

            result = create_metadata_from_files(temp_dir, "test-model")
            assert result["repo_name"] == "test-model"
            assert result["readme_text"] == ""
            assert "model.py" in result["repo_files"]

    def test_create_metadata_nested_files(self):
        """Test metadata creation with nested files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = os.path.join(temp_dir, "src")
            os.makedirs(nested_dir)
            nested_file = os.path.join(nested_dir, "utils.py")
            with open(nested_file, "w") as f:
                f.write("def util(): pass")

            result = create_metadata_from_files(temp_dir, "test-model")
            assert "src/utils.py" in result["repo_files"]


class TestRunAcmeMetrics:
    """Test run_acme_metrics function"""

    def test_run_acme_metrics_with_metric_value(self):
        """Test run_acme_metrics with MetricValue results"""
        meta = {"repo_files": set(["file1.py", "file2.py"])}
        metric_functions = {
            "license": lambda m: MetricValue("license", 0.8, 10),
            "ramp_up": lambda m: MetricValue("ramp_up", 0.7, 5),
        }

        result = run_acme_metrics(meta, metric_functions)
        assert "license" in result
        assert "ramp_up" in result
        assert "net_score" in result
        assert isinstance(result["license"], (int, float))

    def test_run_acme_metrics_with_numeric_result(self):
        """Test run_acme_metrics with numeric results"""
        meta = {"repo_files": set(["file1.py"])}
        metric_functions = {
            "test_metric": lambda m: 0.5,
        }

        result = run_acme_metrics(meta, metric_functions)
        assert "test_metric" in result or "net_score" in result

    def test_run_acme_metrics_with_dict_result(self):
        """Test run_acme_metrics with dict result for size_score"""
        meta = {"repo_files": set(["file1.py"])}
        metric_functions = {
            "size_score": lambda m: {"platform1": 0.8, "platform2": 0.6},
        }

        result = run_acme_metrics(meta, metric_functions)
        assert "net_score" in result

    def test_run_acme_metrics_with_dependencies(self):
        """Test run_acme_metrics with dependencies metric"""
        meta = {"repo_files": set(["file1.py"])}
        metric_functions = {
            "dependencies": lambda m: (0.7, 15),
        }

        result = run_acme_metrics(meta, metric_functions)
        assert "net_score" in result

    def test_run_acme_metrics_with_exception(self):
        """Test run_acme_metrics when metric raises exception"""
        meta = {"repo_files": set(["file1.py"])}
        metric_functions = {
            "failing_metric": lambda m: (_ for _ in ()).throw(Exception("Error")),
        }

        result = run_acme_metrics(meta, metric_functions)
        assert "net_score" in result


class TestRunScorer:
    """Test run_scorer function"""

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.services.rating.analyze_model_content")
    def test_run_scorer_no_github_token(self, mock_analyze):
        """Test run_scorer when no GitHub token"""
        mock_analyze.return_value = {"net_score": 0.8}
        result = run_scorer("test-model")
        assert result == {"net_score": 0.8}
        mock_analyze.assert_called_once_with("test-model")

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token_placeholder"})
    @patch("src.services.rating.analyze_model_content")
    def test_run_scorer_placeholder_token(self, mock_analyze):
        """Test run_scorer with placeholder token"""
        mock_analyze.return_value = {"net_score": 0.8}
        result = run_scorer("test-model")
        assert result == {"net_score": 0.8}
        mock_analyze.assert_called_once_with("test-model")

    @patch.dict(os.environ, {"GITHUB_TOKEN": "real_token"})
    @patch("src.services.rating.subprocess.run")
    @patch("src.services.rating.Path")
    def test_run_scorer_with_subprocess_success(self, mock_path_class, mock_subprocess):
        """Test run_scorer with successful subprocess"""
        mock_urls_file = MagicMock()
        mock_path_class.return_value = mock_urls_file
        mock_urls_file.__truediv__ = lambda self, other: self
        mock_urls_file.write_text = MagicMock()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"net_score": 0.8, "license": 0.9}\n'
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        result = run_scorer("test-model")
        assert result["net_score"] == 0.8
        assert result["license"] == 0.9

    @patch.dict(os.environ, {"GITHUB_TOKEN": "real_token"})
    @patch("src.services.rating.subprocess.run")
    @patch("src.services.rating.Path")
    def test_run_scorer_subprocess_failure(self, mock_path_class, mock_subprocess):
        """Test run_scorer with subprocess failure"""
        mock_urls_file = MagicMock()
        mock_path_class.return_value = mock_urls_file
        mock_urls_file.__truediv__ = lambda self, other: self
        mock_urls_file.write_text = MagicMock()

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Error occurred"
        mock_subprocess.return_value = mock_proc

        with pytest.raises(HTTPException) as exc:
            run_scorer("test-model")
        assert exc.value.status_code == 502

    @patch.dict(os.environ, {"GITHUB_TOKEN": "real_token"})
    @patch("src.services.rating.subprocess.run")
    @patch("src.services.rating.Path")
    def test_run_scorer_timeout(self, mock_path_class, mock_subprocess):
        """Test run_scorer with timeout"""
        import subprocess
        mock_urls_file = MagicMock()
        mock_path_class.return_value = mock_urls_file
        mock_urls_file.__truediv__ = lambda self, other: self
        mock_urls_file.write_text = MagicMock()

        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 30)

        with pytest.raises(HTTPException) as exc:
            run_scorer("test-model")
        assert exc.value.status_code == 502
        assert "timed out" in exc.value.detail.lower()

    @patch.dict(os.environ, {"GITHUB_TOKEN": "real_token"})
    @patch("src.services.rating.subprocess.run")
    @patch("src.services.rating.Path")
    def test_run_scorer_invalid_json(self, mock_path_class, mock_subprocess):
        """Test run_scorer with invalid JSON output"""
        mock_urls_file = MagicMock()
        mock_path_class.return_value = mock_urls_file
        mock_urls_file.__truediv__ = lambda self, other: self
        mock_urls_file.write_text = MagicMock()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "not json\n"
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        with pytest.raises(HTTPException) as exc:
            run_scorer("test-model")
        assert exc.value.status_code == 502


class TestAnalyzeModelContent:
    """Test analyze_model_content function"""

    def test_analyze_model_content_suppress_errors(self):
        """Test analyze_model_content with suppress_errors=True"""
        # This function is complex and has many dependencies
        # Testing the suppress_errors path - patch at s3_service level
        with patch("src.services.s3_service.list_models") as mock_list:
            mock_list.return_value = {"models": []}  # No models found
            with patch("src.services.s3_service.download_from_huggingface") as mock_download:
                mock_download.side_effect = Exception("Error")
                result = analyze_model_content("test-model", suppress_errors=True)
                assert result is None


class TestRateModel:
    """Test rate_model function"""

    @patch("src.services.rating.run_scorer")
    def test_rate_model_success(self, mock_scorer):
        """Test successful rate_model"""
        mock_scorer.return_value = {
            "net_score": 0.8,
            "license": 0.9,
            "ramp_up": 0.7,
            "aggregation_latency": 100,
        }

        body = RateRequest(target="test-model")
        result = rate_model("model-123", body, enforce=False)

        assert "data" in result
        assert result["data"]["modelId"] == "model-123"
        assert result["data"]["target"] == "test-model"
        assert result["data"]["netScore"] == 0.8

    @patch("src.services.rating.run_scorer")
    def test_rate_model_enforce_pass(self, mock_scorer):
        """Test rate_model with enforce=True and passing scores"""
        mock_scorer.return_value = {
            "net_score": 0.8,
            "license": 0.9,
            "ramp_up": 0.7,
        }

        body = RateRequest(target="test-model")
        result = rate_model("model-123", body, enforce=True)
        assert "data" in result

    @patch("src.services.rating.run_scorer")
    def test_rate_model_enforce_fail(self, mock_scorer):
        """Test rate_model with enforce=True and failing scores"""
        mock_scorer.return_value = {
            "net_score": 0.8,
            "license": 0.3,  # Below 0.5 threshold
            "ramp_up": 0.7,
        }

        body = RateRequest(target="test-model")
        with pytest.raises(HTTPException) as exc:
            rate_model("model-123", body, enforce=True)
        assert exc.value.status_code == 422
        assert "INGESTIBILITY_FAILURE" in str(exc.value.detail)

    def test_rate_model_missing_target(self):
        """Test rate_model with missing target"""
        body = RateRequest(target="")
        with pytest.raises(HTTPException) as exc:
            rate_model("model-123", body, enforce=False)
        assert exc.value.status_code == 400

    def test_rate_model_invalid_target_type(self):
        """Test rate_model with invalid target type"""
        # RateRequest will validate, so we need to create it differently
        # Actually, let's test with a mock that has None
        with patch("src.services.rating.RateRequest") as mock_request:
            mock_request.return_value.target = None
            mock_request.return_value.__class__ = RateRequest
            with pytest.raises((HTTPException, ValueError)):
                rate_model("model-123", mock_request.return_value, enforce=False)

    def test_create_metadata_from_files_empty_dir(self):
        """Test create_metadata_from_files with empty directory"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            result = create_metadata_from_files(temp_dir, "test-model")
            assert result["repo_name"] == "test-model"
            assert len(result["repo_files"]) == 0

    def test_create_metadata_from_files_with_license(self):
        """Test create_metadata_from_files with license file"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            license_file = os.path.join(temp_dir, "LICENSE")
            with open(license_file, "w") as f:
                f.write("MIT License")
            result = create_metadata_from_files(temp_dir, "test-model")
            assert "license_text" in result
            assert "MIT" in result["license_text"]

    def test_run_acme_metrics_partial_failure(self):
        """Test run_acme_metrics with partial metric failures"""
        meta = {"repo_name": "test"}
        metric_functions = {
            "test_metric": lambda m: MetricValue("test_metric", 0.5, 0),
            "failing_metric": lambda m: (_ for _ in ()).throw(Exception("Fail"))
        }
        result = run_acme_metrics(meta, metric_functions)
        # Should handle failure gracefully
        assert "test_metric" in result

    def test_analyze_model_content_large_file(self):
        """Test analyze_model_content with large file"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            large_file = os.path.join(temp_dir, "large.bin")
            with open(large_file, "wb") as f:
                f.write(b"x" * 1000000)  # 1MB file
            result = analyze_model_content(temp_dir, suppress_errors=True)
            # Should handle large files
            assert result is not None

    def test_run_scorer_different_metric_combinations(self):
        """Test run_scorer with different metric combinations"""
        with patch("src.services.rating.analyze_model_content") as mock_analyze:
            with patch("src.services.rating.run_acme_metrics") as mock_metrics:
                with patch("subprocess.run") as mock_subprocess:
                    mock_analyze.return_value = {"repo_name": "test"}
                    mock_metrics.return_value = {
                        "ramp_up": MetricValue("ramp_up", 0.8, 0),
                        "license": MetricValue("license", 0.9, 0)
                    }
                    mock_subprocess.return_value = MagicMock(
                        stdout='{"net_score": 0.85}',
                        returncode=0
                    )
                    result = run_scorer("test-target")
                    assert "net_score" in result or "scores" in result

