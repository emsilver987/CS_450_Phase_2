#!/usr/bin/env python3
"""
Simple non-interactive test script for LLM integration.
Runs all tests automatically.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    print("="*60)
    print("LLM Integration Test - Running All Tests")
    print("="*60)
    
    from services.llm_service import is_llm_available
    
    if not is_llm_available():
        print("\n[WARNING] LLM not available (API key not set)")
        print("Set GEN_AI_STUDIO_API_KEY in .env file to enable LLM features")
        return
    
    print("\n[OK] LLM is available - running tests...\n")
    
    # Test 1: License Compatibility
    print("\n" + "="*60)
    print("Test 1: License Compatibility Analysis")
    print("="*60)
    try:
        from services.llm_service import analyze_license_compatibility
        
        model_license = "MIT License - Permission is hereby granted..."
        github_license = "Apache License 2.0 - Licensed under the Apache License..."
        
        result = analyze_license_compatibility(
            model_license_text=model_license,
            github_license_text=github_license,
            use_case="fine-tune+inference"
        )
        
        if result:
            print(f"[PASS] Compatible: {result.get('compatible')}")
            print(f"       Reason: {result.get('reason', 'N/A')[:80]}...")
        else:
            print("[FAIL] LLM returned None")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    # Test 2: Keyword Extraction
    print("\n" + "="*60)
    print("Test 2: Model Card Keyword Extraction")
    print("="*60)
    try:
        from services.llm_service import extract_model_card_keywords
        
        model_card = """
        # BERT Base Model
        BERT is a transformer model for NLP tasks including text classification,
        sentiment analysis, and question answering. Achieves 95% accuracy.
        """
        
        keywords = extract_model_card_keywords(model_card)
        
        if keywords:
            print(f"[PASS] Extracted {len(keywords)} keywords:")
            print(f"       {', '.join(keywords[:5])}")
        else:
            print("[FAIL] LLM returned None")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    # Test 3: Error Message Generation
    print("\n" + "="*60)
    print("Test 3: Error Message Generation")
    print("="*60)
    try:
        from services.llm_service import generate_helpful_error_message
        
        message = generate_helpful_error_message(
            error_type="INGESTIBILITY_FAILURE",
            error_context={
                "modelId": "test-model",
                "failed_metrics": {"license": 0.2}
            },
            user_action="Rating model"
        )
        
        if message:
            print(f"[PASS] Generated message:")
            print(f"       {message[:100]}...")
        else:
            print("[FAIL] LLM returned None")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    # Test 4: Integration Test
    print("\n" + "="*60)
    print("Test 4: License Service Integration")
    print("="*60)
    try:
        from services.license_compatibility import check_license_compatibility
        
        result = check_license_compatibility(
            model_license="mit",
            github_license="apache-2",
            use_case="fine-tune+inference"
        )
        
        print(f"[PASS] Compatible: {result.get('compatible')}")
        print(f"       LLM Enhanced: {result.get('llm_enhanced', False)}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == "__main__":
    main()

