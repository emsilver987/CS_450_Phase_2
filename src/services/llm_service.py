"""
LLM Service for Phase 2 - Simple integration for license analysis, 
model card search, and error message improvement.

This service uses Purdue GenAI Studio API to assist with:
1. License compatibility analysis for complex license texts
2. Model card content understanding for semantic search
3. Improved error message generation
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, List
import requests

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Try to find .env file in project root (2 levels up from this file)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        # Use utf-8-sig encoding to handle BOM if present
        load_dotenv(env_path, encoding='utf-8-sig')
    else:
        # Fallback to default location
        load_dotenv()
except ImportError:
    # python-dotenv not installed, that's okay - will use environment variables directly
    pass
except Exception:
    # If loading fails for any reason, continue without .env
    pass

logger = logging.getLogger(__name__)

# Purdue GenAI Studio API configuration
PURDUE_GENAI_API_URL = os.getenv(
    "PURDUE_GENAI_API_URL", 
    "https://genai.rcac.purdue.edu/api/v1/chat/completions"
)
PURDUE_GENAI_MODEL = os.getenv("PURDUE_GENAI_MODEL", "llama3.2:latest")
PURDUE_GENAI_API_KEY = os.getenv("GEN_AI_STUDIO_API_KEY") or os.getenv("PURDUE_GENAI_API_KEY")

# Rate limiting
RATE_LIMIT_DELAY = 1.0  # seconds between requests
_last_request_time = 0.0


def _rate_limit() -> None:
    """Apply rate limiting between requests."""
    global _last_request_time
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - time_since_last)
    _last_request_time = time.time()


def _call_llm_api(prompt: str, system_message: Optional[str] = None) -> Optional[str]:
    """
    Call Purdue GenAI Studio API.
    
    Args:
        prompt: User prompt
        system_message: Optional system message for context
        
    Returns:
        LLM response text or None if API call fails
    """
    if not PURDUE_GENAI_API_KEY:
        logger.debug("LLM API key not set, skipping LLM call")
        return None
    
    _rate_limit()
    
    headers = {
        "Authorization": f"Bearer {PURDUE_GENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": PURDUE_GENAI_MODEL,
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.1,
    }
    
    try:
        response = requests.post(
            PURDUE_GENAI_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract content from response (handle different response formats)
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0].get("message", {}).get("content", "")
        elif "content" in result:
            return result["content"]
        else:
            logger.warning(f"Unexpected LLM API response format: {result}")
            return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"LLM API call failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error in LLM API call: {e}")
        return None


def analyze_license_compatibility(
    model_license_text: str,
    github_license_text: str,
    use_case: str = "fine-tune+inference"
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to analyze license compatibility for complex license texts.
    
    This is used as a fallback when rule-based checking is uncertain.
    
    Args:
        model_license_text: Full text of model license
        github_license_text: Full text of GitHub repository license
        use_case: Intended use case (e.g., "fine-tune+inference")
        
    Returns:
        Dictionary with compatibility analysis or None if LLM unavailable
    """
    system_msg = (
        "You are an expert in software license compatibility analysis. "
        "Analyze license texts and determine compatibility for the specified use case. "
        "Return a JSON object with 'compatible' (boolean), 'reason' (string), "
        "and 'restrictions' (array of strings)."
    )
    
    prompt = f"""Analyze the compatibility of these two licenses for the use case: {use_case}

Model License:
{model_license_text[:2000]}

GitHub Repository License:
{github_license_text[:2000]}

Determine if these licenses are compatible for {use_case}. Consider:
- Fine-tuning creates derived works
- Inference/generation may have different requirements
- Copyleft vs permissive license interactions
- Specific restrictions in license text

Return JSON format:
{{
    "compatible": true/false,
    "reason": "explanation",
    "restrictions": ["restriction1", "restriction2"]
}}"""
    
    response = _call_llm_api(prompt, system_msg)
    if not response:
        return None
    
    try:
        # Try to extract JSON from response
        # LLM might wrap JSON in markdown code blocks
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response)
        return result
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM license analysis response: {response}")
        return None


def extract_model_card_keywords(model_card_text: str) -> Optional[List[str]]:
    """
    Use LLM to extract semantic keywords from model card content for better search.
    
    Args:
        model_card_text: Model card/README text content
        
    Returns:
        List of relevant keywords or None if LLM unavailable
    """
    system_msg = (
        "You are an expert at analyzing AI/ML model documentation. "
        "Extract key terms, concepts, and topics from model cards. "
        "Return a JSON array of relevant keywords."
    )
    
    prompt = f"""Extract key terms and concepts from this model card that would be useful for search:

{model_card_text[:3000]}

Return a JSON array of keywords, focusing on:
- Model architecture/type
- Use cases and applications
- Datasets used
- Performance characteristics
- Technical details

Example: ["transformer", "NLP", "BERT", "text classification", "GLUE benchmark"]

Return only the JSON array, no other text."""
    
    response = _call_llm_api(prompt, system_msg)
    if not response:
        return None
    
    try:
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        keywords = json.loads(response)
        if isinstance(keywords, list):
            return keywords
        return None
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM keyword extraction response: {response}")
        return None


def generate_helpful_error_message(
    error_type: str,
    error_context: Dict[str, Any],
    user_action: str
) -> Optional[str]:
    """
    Use LLM to generate more helpful error messages for users.
    
    Args:
        error_type: Type of error (e.g., "ModelNotFound", "LicenseIncompatible")
        error_context: Context about the error
        user_action: What the user was trying to do
        
    Returns:
        Helpful error message or None if LLM unavailable
    """
    system_msg = (
        "You are a helpful technical support assistant. "
        "Generate clear, accurate, actionable error messages that help users understand "
        "what went wrong and how to fix it. Be precise and avoid mentioning unrelated issues."
    )
    
    # Create a more specific prompt based on error type
    if error_type == "GITHUB_LICENSE_EXTRACTION_FAILED":
        prompt = f"""The user is trying to check license compatibility but cannot fetch the license from a GitHub repository.

GitHub URL: {error_context.get('github_url', 'unknown')}
Model ID: {error_context.get('model_id', 'unknown')}

IMPORTANT: This is NOT a license compatibility issue. The problem is that the license information could not be retrieved from GitHub.

Possible reasons:
{chr(10).join(f"- {cause}" for cause in error_context.get('possible_causes', []))}

Generate a clear, accurate error message that:
1. Clearly states this is a GitHub API/repository access issue, NOT a license compatibility problem
2. Explains the most likely cause based on the context
3. Provides specific, actionable solutions
4. Is concise and professional

Do NOT mention license incompatibility or license mismatches. Focus on the GitHub repository access issue.

Return only the error message text, no JSON or markdown formatting."""
    elif error_type == "MODEL_LICENSE_NOT_FOUND":
        prompt = f"""The user is trying to check license compatibility but the model's license could not be found.

Model ID: {error_context.get('model_id', 'unknown')}
Model Name: {error_context.get('model_name', 'unknown')}

Generate a clear error message explaining that the model's license information is missing and suggest how to resolve it.

Return only the error message text, no JSON or markdown formatting."""
    elif error_type == "LICENSE_CHECK_ERROR":
        prompt = f"""An error occurred while checking license compatibility.

Error: {error_context.get('error', 'unknown error')}
Model ID: {error_context.get('model_id', 'unknown')}
GitHub URL: {error_context.get('github_url', 'unknown')}

Generate a helpful error message that explains what went wrong and suggests how to fix it.

Return only the error message text, no JSON or markdown formatting."""
    else:
        # Generic prompt for other error types
        prompt = f"""Generate a helpful error message for a user experiencing this issue:

Error Type: {error_type}
User Action: {user_action}
Context: {json.dumps(error_context, indent=2)}

Create a clear, concise error message that:
1. Explains what went wrong in simple terms
2. Suggests possible solutions
3. Is friendly and professional

Return only the error message text, no JSON or markdown formatting."""
    
    response = _call_llm_api(prompt, system_msg)
    if response:
        return response.strip()
    return None


def analyze_lineage_config(config_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Use LLM to analyze and extract lineage information from complex config.json files.
    
    Args:
        config_json: Model configuration dictionary
        
    Returns:
        Dictionary with extracted lineage information or None if LLM unavailable
    """
    system_msg = (
        "You are an expert at analyzing AI model configurations. "
        "Extract parent model information and lineage relationships from config files. "
        "Return a JSON object with lineage information."
    )
    
    config_str = json.dumps(config_json, indent=2)[:2000]
    
    prompt = f"""Analyze this model configuration and extract lineage/parent information:

{config_str}

Look for fields like:
- _name_or_path
- base_model_name_or_path
- pretrained_model_name_or_path
- parent_model
- architecture references

Return JSON format:
{{
    "parent_models": ["model1", "model2"],
    "base_architecture": "architecture_name",
    "lineage_notes": "any relevant notes"
}}"""
    
    response = _call_llm_api(prompt, system_msg)
    if not response:
        return None
    
    try:
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response)
        return result
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM lineage analysis response: {response}")
        return None


def is_llm_available() -> bool:
    """Check if LLM service is available (API key is set)."""
    return PURDUE_GENAI_API_KEY is not None and PURDUE_GENAI_API_KEY != ""

