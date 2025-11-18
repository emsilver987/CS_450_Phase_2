"""
Utility module for retrieving JWT secret from AWS Secrets Manager (KMS-encrypted).
Falls back to JWT_SECRET environment variable ONLY in development mode.
In production, fails fast if Secrets Manager is not available.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

# Cache for the JWT secret to avoid repeated Secrets Manager calls
_JWT_SECRET_CACHE: Optional[str] = None
_JWT_SECRET_NAME = os.getenv("JWT_SECRET_NAME", "acme-jwt-secret")
_AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Determine if we're in production mode
_PYTHON_ENV = os.getenv("PYTHON_ENV", "development").lower()
_IS_PRODUCTION = _PYTHON_ENV == "production"


def get_jwt_secret() -> Optional[str]:
    """
    Retrieve JWT secret from AWS Secrets Manager (KMS-encrypted).
    
    In production: Only uses Secrets Manager. Fails if not available.
    In development: Falls back to JWT_SECRET environment variable if Secrets Manager unavailable.
    
    Returns:
        JWT secret string, or None if not available (development only)
    
    Raises:
        RuntimeError: In production if Secrets Manager is not available
    """
    global _JWT_SECRET_CACHE
    
    # Return cached value if available
    if _JWT_SECRET_CACHE is not None:
        return _JWT_SECRET_CACHE
    
    # In production, ONLY use Secrets Manager (no fallbacks)
    # In development, allow fallback to env var for local testing
    if not _IS_PRODUCTION:
        # Development mode: Try environment variable first (for local testing)
        env_secret = os.getenv("JWT_SECRET")
        if env_secret:
            logger.info("Using JWT_SECRET from environment variable (development mode)")
            _JWT_SECRET_CACHE = env_secret
            return env_secret
    
    # Try to get from Secrets Manager
    try:
        secrets_client = boto3.client("secretsmanager", region_name=_AWS_REGION)
        
        try:
            response = secrets_client.get_secret_value(SecretId=_JWT_SECRET_NAME)
            
            # Parse the secret string (it's JSON)
            secret_string = response.get("SecretString")
            if not secret_string:
                raise ValueError("SecretString is empty")
            
            secret_data = json.loads(secret_string)
            jwt_secret = secret_data.get("jwt_secret")
            
            if not jwt_secret:
                raise ValueError("jwt_secret field not found in secret")
            
            logger.info(f"Successfully retrieved JWT secret from Secrets Manager: {_JWT_SECRET_NAME}")
            _JWT_SECRET_CACHE = jwt_secret
            return jwt_secret
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if _IS_PRODUCTION:
                # In production, fail fast - no fallbacks
                if error_code == "ResourceNotFoundException":
                    error_msg = (
                        f"JWT secret '{_JWT_SECRET_NAME}' not found in Secrets Manager. "
                        "This is required in production. Check Secrets Manager configuration."
                    )
                elif error_code == "AccessDeniedException":
                    error_msg = (
                        f"Access denied to Secrets Manager secret '{_JWT_SECRET_NAME}'. "
                        "Check IAM permissions. This is required in production."
                    )
                else:
                    error_msg = (
                        f"Error retrieving JWT secret from Secrets Manager: {e}. "
                        "This is required in production."
                    )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            else:
                # Development mode: Log warning and continue to fallback
                if error_code == "ResourceNotFoundException":
                    logger.warning(
                        f"JWT secret '{_JWT_SECRET_NAME}' not found in Secrets Manager. "
                        "Falling back to environment variable (development mode)."
                    )
                elif error_code == "AccessDeniedException":
                    logger.warning(
                        f"Access denied to Secrets Manager secret '{_JWT_SECRET_NAME}'. "
                        "Falling back to environment variable (development mode)."
                    )
                else:
                    logger.warning(
                        f"Error retrieving JWT secret from Secrets Manager: {e}. "
                        "Falling back to environment variable (development mode)."
                    )
        except (json.JSONDecodeError, ValueError) as e:
            if _IS_PRODUCTION:
                error_msg = (
                    f"Error parsing JWT secret from Secrets Manager: {e}. "
                    "This is required in production."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            else:
                logger.warning(
                    f"Error parsing JWT secret from Secrets Manager: {e}. "
                    "Falling back to environment variable (development mode)."
                )
        except Exception as e:
            if _IS_PRODUCTION:
                error_msg = (
                    f"Unexpected error retrieving JWT secret from Secrets Manager: {e}. "
                    "This is required in production."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            else:
                logger.warning(
                    f"Unexpected error retrieving JWT secret from Secrets Manager: {e}. "
                    "Falling back to environment variable (development mode)."
                )
            
    except (BotoCoreError, Exception) as e:
        if _IS_PRODUCTION:
            error_msg = (
                f"AWS Secrets Manager not available: {e}. "
                "This is required in production. Check AWS credentials and network connectivity."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        else:
            logger.warning(
                f"AWS Secrets Manager not available: {e}. "
                "This is normal for local development. Falling back to environment variable."
            )
    
    # Development mode fallback: Try environment variable or generate temporary secret
    if not _IS_PRODUCTION:
        env_secret = os.getenv("JWT_SECRET")
        if env_secret:
            logger.info("Using JWT_SECRET from environment variable (development fallback)")
            _JWT_SECRET_CACHE = env_secret
            return env_secret
        
        # Last resort: generate a temporary secret (development only)
        import secrets as secrets_module
        fallback_secret = secrets_module.token_urlsafe(32)
        logger.warning(
            "No JWT secret found. Generated a temporary secret for local development. "
            "This should NOT be used in production. Set JWT_SECRET environment variable or configure Secrets Manager."
        )
        _JWT_SECRET_CACHE = fallback_secret
        return fallback_secret
    
    # Production mode: Should never reach here (all errors raise RuntimeError above)
    error_msg = "Failed to retrieve JWT secret and no fallback available in production."
    logger.error(error_msg)
    raise RuntimeError(error_msg)


def clear_jwt_secret_cache() -> None:
    """Clear the JWT secret cache. Useful for testing or secret rotation."""
    global _JWT_SECRET_CACHE
    _JWT_SECRET_CACHE = None


def get_jwt_secret_status() -> dict[str, any]:
    """
    Get the status of JWT secret retrieval (for diagnostics).
    
    Returns a dictionary with:
    - available: bool - Whether secret is available
    - source: str - Where secret came from ("secrets_manager", "env_var", "generated", "none")
    - secret_name: str - Name of the secret in Secrets Manager
    - is_production: bool - Whether running in production mode
    - cached: bool - Whether secret is cached
    
    Note: Does NOT return the actual secret value for security.
    """
    global _JWT_SECRET_CACHE
    
    status = {
        "available": _JWT_SECRET_CACHE is not None,
        "source": "none",
        "secret_name": _JWT_SECRET_NAME,
        "is_production": _IS_PRODUCTION,
        "cached": _JWT_SECRET_CACHE is not None,
    }
    
    if _JWT_SECRET_CACHE is not None:
        # Secret is available - determine source by checking env var first
        env_secret = os.getenv("JWT_SECRET")
        if env_secret and env_secret == _JWT_SECRET_CACHE:
            status["source"] = "env_var"
        else:
            # Must be from Secrets Manager (or generated, but we can't tell)
            # In production, it must be from Secrets Manager
            if _IS_PRODUCTION:
                status["source"] = "secrets_manager"
            else:
                # In development, could be from Secrets Manager or generated
                # We'll assume Secrets Manager if it's not the env var
                status["source"] = "secrets_manager_or_generated"
    else:
        # Check if we can determine source without retrieving
        env_secret = os.getenv("JWT_SECRET")
        if env_secret:
            status["source"] = "env_var_available"
    
    return status

