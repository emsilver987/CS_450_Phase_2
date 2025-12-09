#!/usr/bin/env python3
"""
Quick diagnostic script to check LLM API key configuration.
Run this to verify if the LLM API key is properly set up.
"""

import os
import sys
import json

def check_llm_key():
    """Check LLM API key status"""
    print("=" * 60)
    print("LLM API Key Diagnostic Check")
    print("=" * 60)
    print()
    
    # Check environment variables
    env_vars = {
        "GEN_AI_STUDIO_API_KEY": os.getenv("GEN_AI_STUDIO_API_KEY"),
        "PURDUE_GENAI_API_KEY": os.getenv("PURDUE_GENAI_API_KEY"),
        "GENAI_API_KEY": os.getenv("GENAI_API_KEY"),
    }
    
    print("Environment Variables:")
    for var_name, var_value in env_vars.items():
        if var_value:
            # Don't print the actual key, just show it's set
            print(f"  ✓ {var_name}: SET (length: {len(var_value)})")
            # Show first 4 chars for verification (if long enough)
            if len(var_value) >= 4:
                print(f"    Preview: {var_value[:4]}...")
            # Check if it looks like JSON
            if var_value.strip().startswith("{"):
                print(f"    ⚠ Warning: Value appears to be JSON format")
                try:
                    parsed = json.loads(var_value)
                    if isinstance(parsed, dict):
                        print(f"    JSON keys found: {list(parsed.keys())}")
                except:
                    pass
        else:
            print(f"  ✗ {var_name}: NOT SET")
    print()
    
    # Try to import and check the LLM service
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from services.llm_service import (
            is_llm_available,
            get_api_key_status,
            PURDUE_GENAI_API_URL,
            PURDUE_GENAI_MODEL,
            PURDUE_GENAI_API_KEY
        )
        
        print("LLM Service Status:")
        print(f"  API URL: {PURDUE_GENAI_API_URL}")
        print(f"  Model: {PURDUE_GENAI_MODEL}")
        print()
        
        # Check API key status
        api_status = get_api_key_status()
        print("API Key Status:")
        print(f"  Module-level key set: {api_status['module_key_set']}")
        print(f"  Environment key present: {api_status['env_key_present']}")
        print(f"  API key loaded: {api_status['api_key_loaded']}")
        print()
        
        # Check availability
        is_available = is_llm_available()
        print("LLM Availability:")
        if is_available:
            print(f"  ✓ LLM service is AVAILABLE")
            if PURDUE_GENAI_API_KEY:
                print(f"    API Key length: {len(PURDUE_GENAI_API_KEY)}")
        else:
            print(f"  ✗ LLM service is NOT AVAILABLE")
        print()
        
        # Summary
        print("=" * 60)
        if is_available:
            print("✓ RESULT: LLM API key is properly configured!")
        else:
            print("✗ RESULT: LLM API key is NOT configured.")
            print()
            print("To fix this:")
            print("  1. Set one of these environment variables:")
            print("     - GEN_AI_STUDIO_API_KEY")
            print("     - PURDUE_GENAI_API_KEY")
            print("     - GENAI_API_KEY")
            print("  2. Or configure it in AWS Secrets Manager for ECS deployment")
        print("=" * 60)
        
        return is_available
        
    except ImportError as e:
        print(f"Error importing LLM service: {e}")
        print("Make sure you're running this from the project root directory")
        return False
    except Exception as e:
        print(f"Error checking LLM service: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_llm_key()
    sys.exit(0 if success else 1)



