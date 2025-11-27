"""
LLM Summary Metric - Analyzes README text using LLM client.

This metric extracts README text, calls the LLM client to generate
a summary and risk flags, stores them in metadata, and returns a score.
"""

import time
import logging
from typing import Dict, Any
from ..types import MetricValue

logger = logging.getLogger(__name__)

# Constants
DEFAULT_SCORE = 0.5
RISK_PENALTY_PER_FLAG = 0.05
MIN_SCORE = 0.0
MAX_SCORE = 1.0


class LLMSummaryMetric:
    """
    Metric that uses LLM to analyze README and generate summaries.

    Scores based on:
    - Presence of README text
    - Quality of LLM-generated summary
    - Number of risk flags (fewer is better)
    """

    name = "LLMSummary"

    def score(self, meta: Dict[str, Any]) -> MetricValue:
        """
        Score based on LLM analysis of README.

        Analyzes README text using LLM client to generate summaries and
        identify risk flags. Falls back to stub mode if LLM client is
        unavailable.

        Args:
            meta: Metadata dict containing:
                - readme_text (str, optional): README content to analyze
                - Other metadata fields may be present but are not used

        Returns:
            MetricValue with:
                - name: "LLMSummary"
                - value: Score [0.0, 1.0] based on summary quality and
                  risk flags
                - latency_ms: Time taken in milliseconds

        Side Effects:
            Stores LLM results in meta dict:
                - meta["llm_summary"]: Generated summary text
                - meta["llm_risk_flags"]: List of risk flag strings

        Example:
            >>> metric = LLMSummaryMetric()
            >>> meta = {"readme_text": "# My Model\\n\\nMIT License"}
            >>> result = metric.score(meta)
            >>> assert 0.0 <= result.value <= 1.0
            >>> assert "llm_summary" in meta
        """
        t0 = time.perf_counter()

        # Input validation
        if not isinstance(meta, dict):
            logger.warning(
                "Invalid metadata: expected dict, got %s",
                type(meta).__name__
            )
            return MetricValue(self.name, MIN_SCORE, 0)

        # Extract README text
        readme_text = meta.get("readme_text") or ""
        if not isinstance(readme_text, str):
            readme_text = str(readme_text) if readme_text else ""

        # Import LLM client (lazy import to avoid circular deps)
        try:
            from services.llm_client import LLMClient
            client = LLMClient()
            result = client.analyze_readme(readme_text)
        except ImportError as e:
            # If LLM client import fails, return default score
            logger.warning(
                f"LLM client import failed: {e}. Using default score."
            )
            result = {
                "summary": "LLM analysis unavailable.",
                "risk_flags": ["llm_unavailable"],
                "score": DEFAULT_SCORE
            }
        except Exception as e:
            # If LLM client fails, return default score
            logger.error(
                f"LLM client error: {e}. Using default score.",
                exc_info=True
            )
            result = {
                "summary": "LLM analysis unavailable.",
                "risk_flags": ["llm_unavailable"],
                "score": DEFAULT_SCORE
            }

        # Store LLM results in metadata for downstream use
        meta["llm_summary"] = result.get("summary", "")
        meta["llm_risk_flags"] = result.get("risk_flags", [])

        # Score is based on LLM result quality
        # Higher score = better summary, fewer risk flags
        base_score = result.get("score", DEFAULT_SCORE)
        risk_penalty = len(result.get("risk_flags", [])) * RISK_PENALTY_PER_FLAG
        final_score = max(MIN_SCORE, min(MAX_SCORE, base_score - risk_penalty))

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, round(final_score, 2), latency_ms)
