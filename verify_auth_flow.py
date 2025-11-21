
import asyncio
import os
import sys
import logging
import json
from starlette.requests import Request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.append(os.getcwd())



# Now import the service
try:
    from src.services import auth_public
    from src.utils.admin_password import get_primary_admin_password
except ImportError as e:
    logger.error(f"Import failed: {e}")
    sys.exit(1)

def _build_request(body: dict) -> Request:
    async def receive():
        return {"type": "http.request", "body": json.dumps(body).encode("utf-8")}
    
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/authenticate",
        "headers": [(b"content-type", b"application/json")],
    }
    return Request(scope, receive)

async def verify_authentication_flow():
    logger.info("Verifying Authentication Flow with Secrets Manager Password...")
    
    # 1. Get the actual password from Secrets Manager
    try:
        real_password = get_primary_admin_password()
        logger.info("Successfully retrieved password from Secrets Manager for testing.")
    except Exception as e:
        logger.error(f"Failed to retrieve password: {e}")
        return False

    # 2. Test Success Case
    logger.info("Testing authentication with CORRECT credentials...")
    req_success = _build_request({
        "user": {"name": "ece30861defaultadminuser", "is_admin": True},
        "secret": {"password": real_password}
    })
    
    try:
        resp = await auth_public._authenticate(req_success)
        if resp.status_code == 200:
            token = resp.body.decode("utf-8")
            if token.startswith("bearer "):
                logger.info("SUCCESS: Authentication passed with correct password.")
            else:
                logger.error(f"FAILURE: Authentication passed but returned invalid token format: {token}")
                return False
        else:
            logger.error(f"FAILURE: Authentication failed with status {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"FAILURE: Authentication raised exception: {e}")
        return False

    # 3. Test Failure Case
    logger.info("Testing authentication with INCORRECT credentials...")
    req_fail = _build_request({
        "user": {"name": "ece30861defaultadminuser", "is_admin": True},
        "secret": {"password": "wrong-password-123"}
    })
    
    try:
        await auth_public._authenticate(req_fail)
        logger.error("FAILURE: Authentication should have failed but passed!")
        return False
    except Exception as e:
        # We expect an HTTPException(401)
        if hasattr(e, "status_code") and e.status_code == 401:
            logger.info("SUCCESS: Authentication correctly rejected wrong password.")
        else:
            logger.error(f"FAILURE: Authentication raised unexpected exception: {e}")
            return False

    return True

if __name__ == "__main__":
    if asyncio.run(verify_authentication_flow()):
        logger.info("ALL VERIFICATIONS PASSED")
        sys.exit(0)
    else:
        logger.error("VERIFICATION FAILED")
        sys.exit(1)
