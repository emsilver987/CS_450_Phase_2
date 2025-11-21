"""
Utility module for retrieving Admin Password from AWS Secrets Manager (KMS-encrypted).
Falls back to hardcoded defaults ONLY in development mode.
In production, fails fast if Secrets Manager is not available.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional, List, Set
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

# Cache for the admin passwords to avoid repeated Secrets Manager calls
_ADMIN_PASSWORDS_CACHE: Optional[List[str]] = None
_ADMIN_SECRET_NAME = os.getenv("ADMIN_SECRET_NAME", "ece30861defaultadminuser")
_AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Hardcoded defaults for fallback (development only)
_DEFAULT_PRIMARY = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
_DEFAULT_ALTERNATE = "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"

# Determine if we're in production mode
_PYTHON_ENV = os.getenv("PYTHON_ENV", "development").lower()
_IS_PRODUCTION = _PYTHON_ENV == "production"


def get_admin_passwords() -> List[str]:
    """
    Retrieve Admin Passwords from AWS Secrets Manager.
    
    Returns:
        List of valid admin passwords. The first one is considered the PRIMARY password.
    """
    global _ADMIN_PASSWORDS_CACHE
    
    if _ADMIN_PASSWORDS_CACHE is not None:
        return _ADMIN_PASSWORDS_CACHE
    
    # In production, ONLY use Secrets Manager
    # In development, try Secrets Manager but fall back to defaults
    
    try:
        secrets_client = boto3.client("secretsmanager", region_name=_AWS_REGION)
        
        try:
            response = secrets_client.get_secret_value(SecretId=_ADMIN_SECRET_NAME)
            secret_string = response.get("SecretString")
            
            if not secret_string:
                raise ValueError("SecretString is empty")
            
            secret_data = json.loads(secret_string)
            passwords = secret_data.get("passwords")
            
            if not passwords or not isinstance(passwords, list):
                raise ValueError("'passwords' field not found or not a list in secret")
            
            logger.info(f"Successfully retrieved Admin Passwords from Secrets Manager: {_ADMIN_SECRET_NAME}")
            _ADMIN_PASSWORDS_CACHE = passwords
            return passwords
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            _handle_error(e, error_code, f"Secret '{_ADMIN_SECRET_NAME}' not found or inaccessible")
            
        except (json.JSONDecodeError, ValueError) as e:
            _handle_error(e, "ParseError", f"Error parsing Admin Password secret: {e}")
            
        except Exception as e:
            _handle_error(e, "UnexpectedError", f"Unexpected error retrieving Admin Password: {e}")
            
    except (BotoCoreError, Exception) as e:
        _handle_error(e, "ConnectionError", f"AWS Secrets Manager not available: {e}")
    
    # Fallback (only reached if _handle_error didn't raise)
    logger.warning("Using hardcoded default admin passwords (development fallback)")
    _ADMIN_PASSWORDS_CACHE = [_DEFAULT_PRIMARY, _DEFAULT_ALTERNATE]
    return _ADMIN_PASSWORDS_CACHE


def get_primary_admin_password() -> str:
    """Return the primary admin password (used for resetting the account)."""
    passwords = get_admin_passwords()
    if not passwords:
        # Should not happen given the fallback, but for safety
        return _DEFAULT_PRIMARY
    return passwords[0]


def _handle_error(error: Exception, code: str, message: str) -> None:
    """Handle errors based on environment (raise in prod, log in dev)."""
    if _IS_PRODUCTION:
        full_msg = f"{message}. This is required in production."
        logger.error(full_msg)
        raise RuntimeError(full_msg) from error
    else:
        logger.warning(f"{message}. Falling back to defaults (development mode).")


def clear_admin_password_cache() -> None:
    """Clear the admin password cache."""
    global _ADMIN_PASSWORDS_CACHE
    _ADMIN_PASSWORDS_CACHE = None
