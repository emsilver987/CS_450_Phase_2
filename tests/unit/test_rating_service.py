import pytest
from unittest.mock import MagicMock, patch
from src.services.rating import (
    python_cmd, alias, analyze_model_content, run_acme_metrics, run_scorer, rate_model, RateRequest
)
from src.acmecli.types import MetricValue

def test_python_cmd():
    assert python_cmd() in ["python", "python3"]

def test_alias():
    obj = {"a": 1, "b": 2}
    assert alias(obj, "a", "c") == 1
    assert alias(obj, "c", "b") == 2
    assert alias(obj, "d") is None



@patch("src.services.s3_service.download_model")
@patch("src.services.s3_service.list_models")
@patch("src.services.rating.run_acme_metrics")
@patch("os.walk")
@patch("builtins.open", new_callable=MagicMock)
@patch("src.services.s3_service.extract_config_from_model")
def test_analyze_model_content_s3_found(mock_extract, mock_open, mock_walk, mock_run, mock_list, mock_download):
    mock_list.return_value = {"models": [{"name": "model1", "version": "1.0.0"}]}
    mock_download.return_value = b"zipcontent"
    mock_walk.return_value = [("/tmp", [], ["file1"])]
    mock_open.return_value.__enter__.return_value.read.return_value = "content"
    mock_run.return_value = {"net_score": 0.8}
    
    # Mock zipfile
    with patch("zipfile.ZipFile"):
        result = analyze_model_content("model1")
    
    assert result["net_score"] == 0.8
    mock_download.assert_called()

@patch("src.services.s3_service.download_from_huggingface")
@patch("src.services.s3_service.list_models")
@patch("src.services.rating.run_acme_metrics")
@patch("os.walk")
@patch("builtins.open", new_callable=MagicMock)
def test_analyze_model_content_hf(mock_open, mock_walk, mock_run, mock_list, mock_hf):
    mock_list.return_value = {"models": []}
    mock_hf.return_value = b"zipcontent"
    mock_walk.return_value = [("/tmp", [], ["file1"])]
    mock_open.return_value.__enter__.return_value.read.return_value = "content"
    mock_run.return_value = {"net_score": 0.8}
    
    # Mock zipfile
    with patch("zipfile.ZipFile"):
        result = analyze_model_content("https://huggingface.co/user/model")
    
    assert result["net_score"] == 0.8
    mock_hf.assert_called()

def test_run_acme_metrics():
    meta = {"repo_files": set()}
    metrics = {
        "bus_factor": lambda m: MetricValue("bus_factor", 0.5, 10),
        "license": lambda m: 0.6
    }
    result = run_acme_metrics(meta, metrics)
    assert "net_score" in result
    assert result["bus_factor"] == 0.5
    assert result["license"] == 0.6

@patch("subprocess.run")
def test_run_scorer_subprocess(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = '{"net_score": 0.9}'
    
    # Set GITHUB_TOKEN to trigger subprocess path
    with patch.dict("os.environ", {"GITHUB_TOKEN": "valid_token"}):
        result = run_scorer("target")
        assert result["net_score"] == 0.9

@patch("src.services.rating.run_scorer")
def test_rate_model_endpoint(mock_scorer):
    mock_scorer.return_value = {"net_score": 0.8, "license": 1.0}
    body = RateRequest(target="model1")
    result = rate_model("model1", body)
    assert result["data"]["netScore"] == 0.8

@patch("src.services.rating.run_scorer")
def test_rate_model_enforce_failure(mock_scorer):
    mock_scorer.return_value = {"net_score": 0.4, "license": 0.4}
    body = RateRequest(target="model1")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        rate_model("model1", body, enforce=True)
    assert exc.value.status_code == 422
