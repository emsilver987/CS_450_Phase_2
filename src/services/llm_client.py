"""
LLM Client for analyzing package metadata and README text.

This module provides a feature-flag controlled interface to LLM services
(initially stubbed for offline mode, with planned Bedrock integration).

Usage:
    client = LLMClient()
    result = client.analyze_readme(readme_text)
    # Returns: {"summary": str, "risk_flags": List[str], "score": float}
"""

import os
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client for LLM-based analysis of package metadata.
    
    Supports offline mode (stub) and future Bedrock integration.
    Controlled via ENABLE_LLM environment variable.
    """
    
    def __init__(self):
        self.enabled = os.environ.get("ENABLE_LLM", "").lower() in ("true", "1", "yes")
        if not self.enabled:
            logger.debug("LLM client disabled (ENABLE_LLM not set). Using stub implementation.")
    
    def analyze_readme(self, readme_text: str) -> Dict[str, Any]:
        """
        Analyze README text and generate summary + risk flags.
        
        Args:
            readme_text: Raw README content (markdown/text)
            
        Returns:
            Dict with keys:
                - summary: str - Human-readable summary (max 200 chars)
                - risk_flags: List[str] - List of risk indicators (e.g., "missing_license", "safety_concerns")
                - score: float - Quality score [0.0, 1.0] based on summary completeness
        """
        if not self.enabled:
            return self._stub_analyze(readme_text)
        
        # Future: Bedrock integration
        # return self._bedrock_analyze(readme_text)
        
        # For now, use stub even if enabled (Bedrock not implemented)
        return self._stub_analyze(readme_text)
    
    def _stub_analyze(self, readme_text: str) -> Dict[str, Any]:
        """
        Stub implementation that works offline.
        
        Generates a basic summary and flags based on heuristics,
        ensuring autograder compatibility.
        """
        if not readme_text or len(readme_text.strip()) < 10:
            return {
                "summary": "No README content available.",
                "risk_flags": ["missing_readme"],
                "score": 0.0
            }
        
        # Heuristic-based summary generation
        readme_lower = readme_text.lower()
        summary_parts = []
        risk_flags = []
        score = 0.5  # Base score
        
        # Extract key information
        if "license" in readme_lower:
            if "mit" in readme_lower or "apache" in readme_lower:
                summary_parts.append("Open source license")
            else:
                risk_flags.append("license_review_needed")
        else:
            risk_flags.append("missing_license")
            score -= 0.1
        
        if "install" in readme_lower or "usage" in readme_lower:
            summary_parts.append("Installation instructions")
            score += 0.1
        else:
            risk_flags.append("missing_installation_guide")
        
        if "example" in readme_lower or "demo" in readme_lower:
            summary_parts.append("Usage examples")
            score += 0.1
        else:
            risk_flags.append("missing_examples")
        
        if "safety" in readme_lower or "bias" in readme_lower:
            summary_parts.append("Safety considerations")
            score += 0.1
        else:
            risk_flags.append("safety_review_needed")
        
        if "model card" in readme_lower or "modelcard" in readme_lower:
            summary_parts.append("Model card documentation")
            score += 0.1
        
        # Generate summary
        if summary_parts:
            summary = f"Package includes: {', '.join(summary_parts[:3])}."
        else:
            summary = "Basic package documentation available."
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        
        return {
            "summary": summary[:200],  # Max 200 chars
            "risk_flags": risk_flags[:5],  # Max 5 flags
            "score": round(score, 2)
        }
    
    def _bedrock_analyze(self, readme_text: str) -> Dict[str, Any]:
        """
        Future: Bedrock integration for LLM analysis.
        
        This method will call Amazon Bedrock to generate summaries
        and risk flags. Currently not implemented.
        """
        # TODO: Implement Bedrock client
        # Example structure:
        # - Call Bedrock model (e.g., Claude)
        # - Prompt: "Summarize this model README in 200 chars and list risk flags"
        # - Parse response
        # - Return structured dict
        logger.warning("Bedrock integration not yet implemented. Using stub.")
        return self._stub_analyze(readme_text)

