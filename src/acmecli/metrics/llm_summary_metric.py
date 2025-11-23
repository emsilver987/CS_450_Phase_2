"""
LLM Summary Metric - Analyzes README text using LLM client.

This metric extracts README text, calls the LLM client to generate
a summary and risk flags, stores them in metadata, and returns a score.
"""

import time
from ..types import MetricValue
from .base import register


class LLMSummaryMetric:
    """
    Metric that uses LLM to analyze README and generate summaries.
    
    Scores based on:
    - Presence of README text
    - Quality of LLM-generated summary
    - Number of risk flags (fewer is better)
    """
    
    name = "LLMSummary"
    
    def score(self, meta: dict) -> MetricValue:
        """
        Score based on LLM analysis of README.
        
        Args:
            meta: Metadata dict containing readme_text
            
        Returns:
            MetricValue with score [0.0, 1.0] and latency
        """
        t0 = time.perf_counter()
        
        # Extract README text
        readme_text = meta.get("readme_text") or ""
        
        # Import LLM client (lazy import to avoid circular deps)
        try:
            from services.llm_client import LLMClient
            client = LLMClient()
            result = client.analyze_readme(readme_text)
        except Exception as e:
            # If LLM client fails, return default score
            import logging
            logging.warning(f"LLM client error: {e}. Using default score.")
            result = {
                "summary": "LLM analysis unavailable.",
                "risk_flags": ["llm_unavailable"],
                "score": 0.5
            }
        
        # Store LLM results in metadata for downstream use
        meta["llm_summary"] = result.get("summary", "")
        meta["llm_risk_flags"] = result.get("risk_flags", [])
        
        # Score is based on LLM result quality
        # Higher score = better summary, fewer risk flags
        base_score = result.get("score", 0.5)
        risk_penalty = len(result.get("risk_flags", [])) * 0.05
        final_score = max(0.0, min(1.0, base_score - risk_penalty))
        
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, round(final_score, 2), latency_ms)


# Register the metric
register(LLMSummaryMetric())

