"""
Utility module for retrieving JWT secret from AWS Secrets Manager (KMS-encrypted).
Falls back to JWT_SECRET environment variable for local development.
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


def get_jwt_secret() -> Optional[str]:
    """
    Retrieve JWT secret from AWS Secrets Manager (KMS-encrypted).
    
    Falls back to JWT_SECRET environment variable if:
    - Secrets Manager is not available
    - Secret name is not configured
    - AWS credentials are not available (local development)
    
    Returns:
        JWT secret string, or None if not available
    """
    global _JWT_SECRET_CACHE
    
    # Return cached value if available
    if _JWT_SECRET_CACHE is not None:
        return _JWT_SECRET_CACHE
    
    # First, try environment variable (for local development or override)
    env_secret = os.getenv("JWT_SECRET")
    if env_secret:
        logger.info("Using JWT_SECRET from environment variable")
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
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    f"JWT secret '{_JWT_SECRET_NAME}' not found in Secrets Manager. "
                    "Falling back to environment variable or generating new secret."
                )
            elif error_code == "AccessDeniedException":
                logger.warning(
                    f"Access denied to Secrets Manager secret '{_JWT_SECRET_NAME}'. "
                    "Check IAM permissions. Falling back to environment variable."
                )
            else:
                logger.warning(
                    f"Error retrieving JWT secret from Secrets Manager: {e}. "
                    "Falling back to environment variable."
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Error parsing JWT secret from Secrets Manager: {e}. "
                "Falling back to environment variable."
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error retrieving JWT secret from Secrets Manager: {e}. "
                "Falling back to environment variable."
            )
            
    except (BotoCoreError, Exception) as e:
        logger.warning(
            f"AWS Secrets Manager not available: {e}. "
            "This is normal for local development. Using environment variable or generating new secret."
        )
    
    # Final fallback: generate a new secret (for local development only)
    # This should NOT be used in production
    import secrets as secrets_module
    fallback_secret = secrets_module.token_urlsafe(32)
    logger.warning(
        "No JWT secret found. Generated a temporary secret for local development. "
        "This should NOT be used in production. Set JWT_SECRET environment variable or configure Secrets Manager."
    )
    _JWT_SECRET_CACHE = fallback_secret
    return fallback_secret


def clear_jwt_secret_cache() -> None:
    """Clear the JWT secret cache. Useful for testing or secret rotation."""
    global _JWT_SECRET_CACHE
    _JWT_SECRET_CACHE = None

