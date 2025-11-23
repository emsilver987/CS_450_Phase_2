"""Unit tests for LLM Summary Metric."""
import os
from acmecli.metrics.llm_summary_metric import LLMSummaryMetric


def test_llm_metric_offline_mode():
    """Test that metric works in offline mode (default)."""
    # Ensure LLM is disabled
    os.environ.pop("ENABLE_LLM", None)
    
    metric = LLMSummaryMetric()
    meta = {
        "readme_text": "This is a test README with some content about installation and usage.",
        "name": "test-repo"
    }
    
    result = metric.score(meta)
    
    # Should return a valid score
    assert 0.0 <= result.value <= 1.0
    assert result.latency_ms >= 0
    assert result.name == "LLMSummary"
    
    # Should store values in metadata
    assert "llm_summary" in meta
    assert "llm_risk_flags" in meta
    assert isinstance(meta["llm_summary"], str)
    assert isinstance(meta["llm_risk_flags"], list)
    print(f"✓ Offline mode test passed: score={result.value}, summary={meta['llm_summary'][:50]}")


def test_llm_metric_no_readme():
    """Test metric with empty README."""
    metric = LLMSummaryMetric()
    meta = {"readme_text": "", "name": "empty-repo"}
    
    result = metric.score(meta)
    
    assert 0.0 <= result.value <= 1.0
    assert result.latency_ms >= 0
    assert "llm_summary" in meta
    print(f"✓ Empty README test passed: score={result.value}")


def test_llm_metric_with_license():
    """Test metric with README containing license info."""
    metric = LLMSummaryMetric()
    meta = {
        "readme_text": """
# Test Package

This is a test package with MIT license.

## Installation
pip install test-package

## Usage
Example usage here.
        """,
        "name": "licensed-repo"
    }
    
    result = metric.score(meta)
    
    assert 0.0 <= result.value <= 1.0
    assert "llm_summary" in meta
    assert len(meta["llm_summary"]) > 0
    print(f"✓ License test passed: score={result.value}, summary={meta['llm_summary']}")


def test_llm_metric_metadata_storage():
    """Test that metric stores llm_summary and llm_risk_flags in meta."""
    metric = LLMSummaryMetric()
    meta = {
        "readme_text": "A comprehensive README with installation instructions and examples.",
        "name": "good-repo"
    }
    
    result = metric.score(meta)
    
    # Metadata should have LLM fields
    assert "llm_summary" in meta
    assert "llm_risk_flags" in meta
    assert isinstance(meta["llm_summary"], str)
    assert isinstance(meta["llm_risk_flags"], list)
    
    # Risk flags should be a list of strings
    for flag in meta["llm_risk_flags"]:
        assert isinstance(flag, str)
    
    print(f"✓ Metadata storage test passed")
    print(f"  Summary: {meta['llm_summary']}")
    print(f"  Risk flags: {meta['llm_risk_flags']}")


def test_llm_metric_score_range():
    """Test that scores are properly bounded."""
    metric = LLMSummaryMetric()
    
    test_cases = [
        {"readme_text": "", "name": "empty"},
        {"readme_text": "Short", "name": "short"},
        {"readme_text": "MIT license, install, usage, examples, safety", "name": "complete"},
    ]
    
    for meta in test_cases:
        result = metric.score(meta)
        assert 0.0 <= result.value <= 1.0, f"Score {result.value} out of range for {meta['name']}"
        assert result.latency_ms >= 0
    
    print(f"✓ Score range test passed for {len(test_cases)} cases")


if __name__ == "__main__":
    print("Running LLM Summary Metric Tests...\n")
    test_llm_metric_offline_mode()
    test_llm_metric_no_readme()
    test_llm_metric_with_license()
    test_llm_metric_metadata_storage()
    test_llm_metric_score_range()
    print("\n✅ All tests passed!")
