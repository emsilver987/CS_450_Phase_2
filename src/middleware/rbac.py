"""
RBAC (Role-Based Access Control) Middleware

This module provides middleware and dependency functions for enforcing role-based
access control. It validates user roles against the database to prevent privilege
escalation attacks through JWT token manipulation.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Import auth_service functions - handle both relative and absolute imports
try:
    # Try relative import first (works when imported as module)
    from ..services.auth_service import verify_jwt_token, get_user_by_username, USERS_TABLE
except (ImportError, ValueError):
    # Fallback for absolute import (when running as script or different import context)
    try:
        from src.services.auth_service import verify_jwt_token, get_user_by_username, USERS_TABLE
    except ImportError:
        # Last resort: try adding parent directory to path
        import sys
        from pathlib import Path
        parent_dir = str(Path(__file__).parent.parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from src.services.auth_service import verify_jwt_token, get_user_by_username, USERS_TABLE
import boto3

logger = logging.getLogger(__name__)

security = HTTPBearer()

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))


def verify_admin_role_from_db(user_id: str, username: str) -> bool:
    """
    Verify admin role by checking the database, not just JWT token claims.
    This prevents privilege escalation through JWT token manipulation.
    
    Args:
        user_id: User ID from JWT token
        username: Username from JWT token
        
    Returns:
        True if user has admin role in database, False otherwise
    """
    try:
        # First try to get user by user_id
        users_table = dynamodb.Table(USERS_TABLE)
        response = users_table.get_item(Key={"user_id": user_id})
        
        if "Item" in response:
            user = response["Item"]
            roles = user.get("roles", [])
            # Check if user has admin role in database
            if "admin" in roles:
                logger.info(f"Admin role verified from database for user_id: {user_id}, username: {username}")
                return True
        
        # Fallback: try to get user by username
        user = get_user_by_username(username)
        if user:
            roles = user.get("roles", [])
            if "admin" in roles:
                logger.info(f"Admin role verified from database for username: {username}")
                return True
        
        # Special case: default admin username
        if username == "ece30861defaultadminuser":
            logger.info(f"Default admin username verified: {username}")
            return True
        
        logger.warning(f"Admin role verification failed for user_id: {user_id}, username: {username}")
        return False
    except Exception as e:
        logger.error(f"Error verifying admin role from database: {str(e)}")
        # Fail securely: deny access if we can't verify
        return False


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Dependency function that requires admin privileges.
    Validates JWT token and checks admin role against database.
    
    This prevents privilege escalation by:
    1. Verifying JWT token signature and expiration
    2. Checking user roles in database (not just JWT claims)
    3. Logging all admin access attempts
    
    Returns:
        User data dictionary if admin access is granted
        
    Raises:
        HTTPException(401): If authentication fails or user is not admin
    """
    token = credentials.credentials
    
    # Verify JWT token
    payload = verify_jwt_token(token)
    if not payload:
        logger.warning("Admin access denied: Invalid or expired JWT token")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )
    
    user_id = payload.get("user_id")
    username = payload.get("username")
    
    if not user_id and not username:
        logger.warning("Admin access denied: Missing user_id or username in token")
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing user identification"
        )
    
    # Verify admin role from database (not just JWT claims)
    # This is critical to prevent privilege escalation
    is_admin = verify_admin_role_from_db(user_id or "", username or "")
    
    if not is_admin:
        logger.warning(
            f"Admin access denied: User {username} (user_id: {user_id}) does not have admin role in database"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    # Log successful admin access
    logger.info(
        f"Admin access granted: User {username} (user_id: {user_id}) accessed admin endpoint"
    )
    
    return {
        "user_id": user_id,
        "username": username,
        "roles": payload.get("roles", []),
        "groups": payload.get("groups", []),
        "is_admin": True
    }


def log_admin_operation(
    operation: str,
    user: Dict[str, Any],
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log admin operations for audit trail and non-repudiation.
    
    Args:
        operation: Name of the admin operation (e.g., "reset_system", "delete_user")
        user: User data dictionary from require_admin dependency
        details: Optional additional details about the operation
    """
    try:
        from datetime import datetime, timezone
        
        # Log to CloudWatch/application logs
        log_entry = {
            "event_type": "admin_operation",
            "operation": operation,
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if details:
            log_entry["details"] = details
        
        logger.info(f"ADMIN_OPERATION: {log_entry}")
        
        # Optionally log to DynamoDB audit table
        # This would require adding a downloads/audit table entry
        # For now, we rely on CloudWatch logs
        
    except Exception as e:
        logger.error(f"Error logging admin operation: {str(e)}")
        # Don't fail the operation if logging fails

