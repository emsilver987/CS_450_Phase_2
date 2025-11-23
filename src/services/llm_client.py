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
        self.bedrock_client = None
        self.model_id = os.environ.get("LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        
        if self.enabled:
            logger.info("LLM client enabled - attempting Bedrock initialization...")
            try:
                import boto3
                self.bedrock_client = boto3.client(
                    service_name='bedrock-runtime',
                    region_name=self.region
                )
                logger.info(f"✅ Bedrock client initialized successfully (model: {self.model_id}, region: {self.region})")
            except ImportError:
                logger.warning("boto3 not installed - falling back to stub mode. Install with: pip install boto3")
                self.enabled = False
            except Exception as e:
                logger.warning(f"Failed to initialize Bedrock client: {e}. Falling back to stub mode.")
                self.enabled = False
        else:
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
        if not self.enabled or not self.bedrock_client:
            return self._stub_analyze(readme_text)
        
        # Use Bedrock for real LLM analysis
        try:
            return self._bedrock_analyze(readme_text)
        except Exception as e:
            logger.error(f"Bedrock analysis failed: {e}. Falling back to stub mode.")
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
        Bedrock integration for LLM analysis using Claude.
        
        Calls Amazon Bedrock with Claude to generate intelligent summaries
        and risk flags based on README content.
        """
        import json
        
        if not readme_text or len(readme_text.strip()) < 50:
            return {
                "summary": "README too short for LLM analysis.",
                "risk_flags": ["insufficient_documentation"],
                "score": 0.2
            }
        
        # Truncate README to avoid token limits (~3000 chars = ~750 tokens)
        truncated_readme = readme_text[:3000]
        if len(readme_text) > 3000:
            truncated_readme += "\n\n[... README truncated for analysis ...]"
        
        # Construct prompt for Claude
        prompt = f"""Analyze this repository README and provide:
1. A concise 2-sentence summary of what this package/model does
2. A list of risk flags (security concerns, missing license, unclear purpose, safety issues, etc.)

README Content:
{truncated_readme}

Respond in this EXACT format (no additional text):
SUMMARY: <your 2-sentence summary here>
RISK_FLAGS: <comma-separated list of specific flags, or "none" if no issues>

Be specific with risk flags. Examples: "missing_license", "no_installation_guide", "safety_concerns_not_addressed", "unclear_purpose", "deprecated_dependencies"
"""
        
        try:
            # Call Bedrock with Claude
            logger.debug(f"Calling Bedrock model: {self.model_id}")
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3  # Lower temperature for more consistent output
                })
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [{}])[0].get('text', '')
            
            logger.debug(f"Bedrock response: {content[:200]}...")
            
            # Extract summary and risk flags
            summary = ""
            risk_flags = []
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('SUMMARY:'):
                    summary = line.replace('SUMMARY:', '').strip()
                elif line.startswith('RISK_FLAGS:'):
                    flags_str = line.replace('RISK_FLAGS:', '').strip()
                    if flags_str.lower() != 'none':
                        risk_flags = [f.strip() for f in flags_str.split(',') if f.strip()]
            
            # Validate summary
            if not summary or len(summary) < 10:
                logger.warning("LLM returned invalid summary, using fallback")
                summary = "Package documentation available but summary generation failed."
            
            # Truncate summary to 200 chars
            if len(summary) > 200:
                summary = summary[:197] + "..."
            
            # Calculate score based on analysis
            score = 0.5  # Base score
            
            # Reward good summary
            if len(summary) > 20 and "failed" not in summary.lower():
                score += 0.3
            
            # Penalize risk flags
            if len(risk_flags) == 0:
                score += 0.2
            elif len(risk_flags) <= 2:
                score += 0.1
            else:
                score -= 0.1 * (len(risk_flags) - 2)
            
            # Clamp score
            score = max(0.0, min(1.0, score))
            
            logger.info(f"✅ Bedrock analysis complete: score={score:.2f}, flags={len(risk_flags)}")
            
            return {
                "summary": summary,
                "risk_flags": risk_flags[:5],  # Max 5 flags
                "score": round(score, 2)
            }
            
        except Exception as e:
            logger.error(f"Bedrock API call failed: {e}")
            # Fall back to stub on error
            return self._stub_analyze(readme_text)


