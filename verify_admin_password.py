
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.append(os.getcwd())

def verify_admin_password_retrieval():
    logger.info("Verifying Admin Password Retrieval...")
    
    try:
        from src.utils.admin_password import get_admin_passwords, get_primary_admin_password
        
        # 1. Test get_admin_passwords
        passwords = get_admin_passwords()
        logger.info(f"Retrieved {len(passwords)} passwords.")
        
        if not passwords:
            logger.error("No passwords retrieved!")
            return False
            
        # 2. Test get_primary_admin_password
        primary = get_primary_admin_password()
        logger.info("Retrieved primary password.")
        
        if primary != passwords[0]:
            logger.error("Primary password does not match the first password in the list!")
            return False
            
        # 3. Verify against expected values (since we know what's in the secret)
        expected_primary_start = "correcthorsebatterystaple123"
        if not primary.startswith(expected_primary_start):
            logger.error(f"Primary password does not start with expected prefix '{expected_primary_start}'")
            return False
            
        logger.info("Admin Password Retrieval Verified Successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Verification failed with error: {e}")
        return False

if __name__ == "__main__":
    if verify_admin_password_retrieval():
        sys.exit(0)
    else:
        sys.exit(1)
