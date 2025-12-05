"""
LLM Service for Phase 2 - Simple integration for license analysis, 
model card search, error message improvement, lineage extraction, and treescore calculation.

This service uses Purdue GenAI Studio API to assist with:
1. License compatibility analysis for complex license texts
2. Model card content understanding for semantic search
3. Improved error message generation
4. Lineage extraction from complex config.json files
5. Treescore calculation (supply-chain health score) from lineage information
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

# Load API key - check both environment variable names
# In AWS ECS, the secret is injected as GEN_AI_STUDIO_API_KEY
# Also support PURDUE_GENAI_API_KEY for backward compatibility
def _load_api_key() -> Optional[str]:
    """Load API key from environment variables, handling JSON secrets if needed."""
    api_key = os.getenv("GEN_AI_STUDIO_API_KEY") or os.getenv("PURDUE_GENAI_API_KEY")
    
    if not api_key:
        return None
    
    # If the secret is stored as JSON in AWS Secrets Manager, ECS might inject it as JSON string
    # Try to parse it if it looks like JSON
    if api_key.strip().startswith("{"):
        try:
            parsed = json.loads(api_key)
            # Check if it's a JSON object with the key
            if isinstance(parsed, dict):
                api_key = parsed.get("GEN_AI_STUDIO_API_KEY") or parsed.get("PURDUE_GENAI_API_KEY") or api_key
        except (json.JSONDecodeError, TypeError):
            # Not JSON, use as-is
            pass
    
    return api_key.strip() if api_key else None

# Purdue GenAI Studio API configuration
PURDUE_GENAI_API_URL = os.getenv(
    "PURDUE_GENAI_API_URL", 
    "https://genai.rcac.purdue.edu/api/v1/chat/completions"
)
PURDUE_GENAI_MODEL = os.getenv("PURDUE_GENAI_MODEL", "llama3.2:latest")
PURDUE_GENAI_API_KEY = _load_api_key()

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
    
    This is used as a fallback when rule-based parsing doesn't find lineage information.
    
    Args:
        config_json: Model configuration dictionary
        
    Returns:
        Dictionary with extracted lineage information or None if LLM unavailable or fails
    """
    try:
        if not config_json or not isinstance(config_json, dict):
            logger.debug("Invalid config_json provided to analyze_lineage_config")
            return None
        
        system_msg = (
            "You are an expert at analyzing AI model configurations. "
            "Extract parent model information and lineage relationships from config files. "
            "Return a JSON object with lineage information."
        )
        
        try:
            config_str = json.dumps(config_json, indent=2)[:2000]
        except (TypeError, ValueError) as json_error:
            logger.warning(f"Failed to serialize config_json: {json_error}")
            return None
        
        prompt = f"""Analyze this model configuration and extract lineage/parent information:

{config_str}

Look for fields like:
- _name_or_path
- base_model_name_or_path
- pretrained_model_name_or_path
- parent_model
- base_model
- parent
- from_pretrained
- model_name_or_path
- source_model
- original_model
- foundation_model
- backbone
- teacher_model
- student_model
- checkpoint
- checkpoint_path
- init_checkpoint
- load_from
- from_checkpoint
- resume_from
- transfer_from
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
            if not isinstance(result, dict):
                logger.warning(f"LLM lineage response is not a dict: {type(result)}")
                return None
            return result
        except json.JSONDecodeError as json_error:
            logger.warning(f"Failed to parse LLM lineage analysis response: {json_error}")
            return None
        except Exception as parse_error:
            logger.warning(f"Unexpected error parsing LLM lineage response: {parse_error}")
            return None
    except Exception as e:
        # Catch any other unexpected errors (e.g., in prompt construction)
        logger.warning(f"Unexpected error in analyze_lineage_config: {e}", exc_info=True)
        return None


def calculate_treescore(
    config_json: Dict[str, Any],
    parent_scores: Optional[Dict[str, float]] = None,
    uploaded_models: Optional[List[str]] = None
) -> Optional[float]:
    """
    Use LLM to calculate treescore (supply-chain health score) from lineage information.
    
    Treescore is the average of the total model scores (net_score) of all parents
    according to the lineage graph. This is used as a fallback when rule-based
    calculation is uncertain or when lineage extraction needs LLM assistance.
    
    Args:
        config_json: Model configuration dictionary
        parent_scores: Optional dictionary mapping parent model IDs to their net_scores
        uploaded_models: Optional list of model IDs currently uploaded to the system
        
    Returns:
        Treescore value (0.0-1.0) or None if LLM unavailable or fails
    """
    try:
        if not config_json or not isinstance(config_json, dict):
            logger.debug("Invalid config_json provided to calculate_treescore")
            return None
        
        system_msg = (
            "You are an expert at analyzing AI model lineage and calculating supply-chain health scores. "
            "Extract lineage from config.json and calculate treescore as the average of parent net_scores. "
            "Return a JSON object with the treescore value."
        )
        
        try:
            config_str = json.dumps(config_json, indent=2)[:2000]
        except (TypeError, ValueError) as json_error:
            logger.warning(f"Failed to serialize config_json: {json_error}")
            return None
        
        try:
            parent_scores_str = json.dumps(parent_scores or {}, indent=2) if parent_scores else "{}"
            uploaded_models_str = json.dumps(uploaded_models or [], indent=2) if uploaded_models else "[]"
        except (TypeError, ValueError) as json_error:
            logger.warning(f"Failed to serialize parent_scores or uploaded_models: {json_error}")
            # Continue with empty strings if serialization fails
            parent_scores_str = "{}"
            uploaded_models_str = "[]"
        
        prompt = f"""Analyze this model configuration to extract lineage and calculate treescore.

Config.json:
{config_str}

Parent Scores (net_score for uploaded parents):
{parent_scores_str}

Uploaded Models (check if parents are in this list):
{uploaded_models_str}

TASK 1: Extract lineage graph from config.json
Look for parent model fields like:
- base_model_name_or_path
- _name_or_path
- parent_model
- pretrained_model_name_or_path
- base_model
- parent
- from_pretrained
- model_name_or_path
- source_model
- original_model
- foundation_model
- backbone
- teacher_model
- student_model
- checkpoint
- checkpoint_path
- init_checkpoint
- load_from
- from_checkpoint
- resume_from
- transfer_from

TASK 2: Calculate Treescore
Treescore = average of net_scores of all parents that are:
1. Found in the lineage graph (from config.json)
2. Currently uploaded to the system (in uploaded_models list)
3. Have scores available (in parent_scores dictionary)

Rules:
- If no parents found in lineage graph → treescore = 0.5
- If parents found but none are uploaded to system → treescore = 0.5
- If parents found and uploaded but no scores available → treescore = 0.5
- Otherwise → treescore = average of available parent net_scores (must be between 0.0 and 1.0)

Return JSON format:
{{
    "parent_models_found": ["parent1", "parent2"],
    "uploaded_parents": ["parent1"],
    "parent_scores_used": {{"parent1": 0.85}},
    "treescore": 0.85
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
            if not isinstance(result, dict):
                logger.warning(f"LLM treescore response is not a dict: {type(result)}")
                return None
            
            treescore = result.get("treescore") or result.get("tree_score") or result.get("score")
            
            if treescore is not None:
                try:
                    score = float(treescore)
                    # Clamp to valid range
                    score = max(0.0, min(1.0, score))
                    return round(score, 2)
                except (TypeError, ValueError) as convert_error:
                    logger.warning(f"Invalid treescore value from LLM: {treescore} (error: {convert_error})")
                    return None
            
            return None
        except json.JSONDecodeError as json_error:
            logger.warning(f"Failed to parse LLM treescore calculation response: {json_error}")
            return None
        except Exception as parse_error:
            logger.warning(f"Unexpected error parsing LLM treescore response: {parse_error}")
            return None
    except Exception as e:
        # Catch any other unexpected errors (e.g., in prompt construction)
        logger.warning(f"Unexpected error in calculate_treescore: {e}", exc_info=True)
        return None


def is_llm_available() -> bool:
    """
    Check if LLM service is available (API key is set).
    
    This function checks both the module-level variable and environment variables
    directly, and logs the status for debugging purposes.
    """
    # Check the module-level variable first
    if PURDUE_GENAI_API_KEY and PURDUE_GENAI_API_KEY.strip() and PURDUE_GENAI_API_KEY != "None":
        logger.debug("LLM API key found in module-level variable")
        return True
    
    # Also check environment variables directly (in case they were set after module load)
    # This is important for AWS ECS where secrets are injected at runtime
    api_key = _load_api_key()
    if api_key and api_key.strip() and api_key != "None":
        # Update the module-level variable for future calls
        global PURDUE_GENAI_API_KEY
        PURDUE_GENAI_API_KEY = api_key
        logger.info("LLM API key found in environment variables - LLM service is available")
        return True
    
    # Log warning only once to avoid spam
    if not hasattr(is_llm_available, '_warned'):
        logger.warning(
            "LLM API key not available - GEN_AI_STUDIO_API_KEY and PURDUE_GENAI_API_KEY are not set. "
            "AI-enhanced features will be disabled."
        )
        is_llm_available._warned = True
    return False

