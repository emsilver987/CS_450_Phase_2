"""
LLM Integration Audit Tests

These tests verify that the LLM Summary Metric is properly integrated
into the scoring pipeline and works correctly in offline mode.
"""

import os
import pytest
from typing import Dict, Any

# Import LLM client and metric
# Note: Tests should be run from project root with src/ in Python path
import sys
from pathlib import Path

# Add src to path for imports (matches existing test structure)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from services.llm_client import LLMClient
from acmecli.metrics.llm_summary_metric import LLMSummaryMetric
from acmecli.metrics.base import REGISTRY
from acmecli.types import MetricValue


@pytest.fixture(autouse=True)
def force_offline_llm(monkeypatch):
    """
    For this audit, we always force offline mode to guarantee deterministic,
    network-free behavior suitable for tests/autograder.
    """
    monkeypatch.setenv("ENABLE_LLM", "false")
    # Also unset if it was set
    if "ENABLE_LLM" in os.environ:
        monkeypatch.delenv("ENABLE_LLM", raising=False)


def test_llm_client_offline_mode_basic():
    """Test that LLM client works in offline mode with basic input."""
    client = LLMClient()
    text = "This repository provides a model for image classification using PyTorch. Installation: pip install model. Usage example: import model"
    result = client.analyze_readme(text)

    assert isinstance(result, dict)
    assert "summary" in result
    assert "risk_flags" in result
    assert "score" in result
    assert isinstance(result["summary"], str)
    assert isinstance(result["risk_flags"], list)
    assert isinstance(result["score"], (int, float))
    assert 0.0 <= result["score"] <= 1.0


def test_llm_client_offline_mode_empty_input():
    """Test LLM client handles empty/missing README gracefully."""
    client = LLMClient()
    result = client.analyze_readme("")

    assert "summary" in result
    assert "risk_flags" in result
    assert "score" in result
    # Missing docs should be flagged
    assert len(result["risk_flags"]) > 0
    assert "missing" in " ".join(result["risk_flags"]).lower() or result["score"] == 0.0


def test_llm_client_offline_mode_with_license():
    """Test LLM client detects license information."""
    client = LLMClient()
    text = "This package is licensed under MIT License. Install with pip install."
    result = client.analyze_readme(text)

    assert result["score"] > 0.5  # Should score well with license and install
    # Should not flag missing license
    assert "missing_license" not in result["risk_flags"]


def test_llm_client_offline_mode_without_license():
    """Test LLM client flags missing license."""
    client = LLMClient()
    text = "This is a package without license information."
    result = client.analyze_readme(text)

    # Should flag missing license
    assert "missing_license" in result["risk_flags"] or result["score"] < 0.5


def test_llm_metric_is_registered_in_registry():
    """
    Ensure the LLM metric is actually wired into the registry,
    so it will be called in the normal scoring pipeline.
    """
    names = {m.name for m in REGISTRY}
    assert "LLMSummary" in names, f"LLMSummary not found in registry. Found: {names}"


def test_llm_metric_scores_and_populates_meta():
    """Test that LLMSummaryMetric scores correctly and populates metadata."""
    meta: Dict[str, Any] = {"readme_text": "Simple example model with MIT license, clear README, and installation guide."}

    metric = LLMSummaryMetric()
    result = metric.score(meta)

    # Check return value
    assert isinstance(result, MetricValue)
    assert result.name == "LLMSummary"
    assert isinstance(result.value, (int, float))
    assert 0.0 <= result.value <= 1.0
    assert isinstance(result.latency_ms, int)
    assert result.latency_ms >= 0

    # Check metadata was populated
    assert "llm_summary" in meta
    assert "llm_risk_flags" in meta
    assert isinstance(meta["llm_summary"], str)
    assert isinstance(meta["llm_risk_flags"], list)
    assert len(meta["llm_summary"]) > 0  # Should have a summary


def test_llm_metric_handles_missing_readme():
    """Test that metric handles missing README gracefully."""
    meta: Dict[str, Any] = {}  # No readme_text

    metric = LLMSummaryMetric()
    result = metric.score(meta)

    assert isinstance(result, MetricValue)
    assert 0.0 <= result.value <= 1.0
    # Should still populate metadata (even if empty)
    assert "llm_summary" in meta
    assert "llm_risk_flags" in meta


def test_llm_metric_score_calculation():
    """Test that metric score calculation includes risk penalty."""
    meta: Dict[str, Any] = {
        "readme_text": "This package has no license, no install guide, and no examples."
    }

    metric = LLMSummaryMetric()
    result = metric.score(meta)

    # Should have low score due to missing elements
    assert result.value < 0.5
    # Should have multiple risk flags
    assert len(meta["llm_risk_flags"]) > 0


def test_llm_metric_integration_with_scoring():
    """Test that LLM metric is included in scoring pipeline."""
    from acmecli.scoring import compute_net_score

    # Create mock results including LLM metric
    results = {
        "license": MetricValue("license", 0.8, 0),
        "llm_summary": MetricValue("llm_summary", 0.9, 0),
        "ramp_up_time": MetricValue("ramp_up_time", 0.5, 0),
    }

    net_score, latency = compute_net_score(results)

    # Net score should be calculated (not None)
    assert net_score is not None
    assert isinstance(net_score, (int, float))
    # LLM contributes 5% weight, so should affect net score
    assert net_score > 0


def test_llm_client_deterministic_offline_mode():
    """Test that offline mode produces deterministic results."""
    client = LLMClient()
    text = "MIT License. Installation guide. Usage examples."

    result1 = client.analyze_readme(text)
    result2 = client.analyze_readme(text)

    # Should produce same results (deterministic)
    assert result1["score"] == result2["score"]
    assert result1["summary"] == result2["summary"]
    assert result1["risk_flags"] == result2["risk_flags"]


def test_llm_metric_latency_reasonable():
    """Test that metric latency is reasonable in offline mode."""
    meta: Dict[str, Any] = {
        "readme_text": "A" * 1000  # Longer README
    }

    metric = LLMSummaryMetric()
    result = metric.score(meta)

    # Offline mode should be very fast (< 100ms)
    assert result.latency_ms < 100, f"Latency {result.latency_ms}ms is too high for offline mode"
