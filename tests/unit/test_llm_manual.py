#!/usr/bin/env python3
"""
Manual test script for LLM integration.
Run this to test LLM features interactively.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_license_compatibility():
    """Test LLM license compatibility analysis."""
    print("\n" + "="*60)
    print("Test: License Compatibility Analysis")
    print("="*60)
    
    from services.llm_service import analyze_license_compatibility, is_llm_available
    
    if not is_llm_available():
        print("[SKIP] LLM not available (API key not set)")
        return
    
    # Test with MIT and Apache licenses
    model_license = """
    MIT License
    
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    """
    
    github_license = """
    Apache License 2.0
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
    """
    
    print("Analyzing MIT (model) vs Apache 2.0 (GitHub) compatibility...")
    result = analyze_license_compatibility(
        model_license_text=model_license,
        github_license_text=github_license,
        use_case="fine-tune+inference"
    )
    
    if result:
        print(f"\n[RESULT]")
        print(f"  Compatible: {result.get('compatible', 'Unknown')}")
        print(f"  Reason: {result.get('reason', 'N/A')}")
        if result.get('restrictions'):
            print(f"  Restrictions: {', '.join(result.get('restrictions', []))}")
    else:
        print("[FAIL] LLM returned None")


def test_model_card_keywords():
    """Test LLM model card keyword extraction."""
    print("\n" + "="*60)
    print("Test: Model Card Keyword Extraction")
    print("="*60)
    
    from services.llm_service import extract_model_card_keywords, is_llm_available
    
    if not is_llm_available():
        print("[SKIP] LLM not available (API key not set)")
        return
    
    model_card = """
    # BERT Base Model
    
    BERT (Bidirectional Encoder Representations from Transformers) is a transformer-based
    machine learning model for natural language processing. This model is pre-trained on
    a large corpus of text data and can be fine-tuned for various NLP tasks.
    
    ## Usage
    
    The model can be used for:
    - Text classification
    - Sentiment analysis
    - Question answering
    - Named entity recognition
    
    ## Performance
    
    Achieves state-of-the-art results on GLUE benchmark with 82.1% accuracy.
    """
    
    print("Extracting keywords from model card...")
    keywords = extract_model_card_keywords(model_card)
    
    if keywords:
        print(f"\n[RESULT] Extracted {len(keywords)} keywords:")
        for i, keyword in enumerate(keywords, 1):
            print(f"  {i}. {keyword}")
    else:
        print("[FAIL] LLM returned None")


def test_error_message():
    """Test LLM error message generation."""
    print("\n" + "="*60)
    print("Test: Error Message Generation")
    print("="*60)
    
    from services.llm_service import generate_helpful_error_message, is_llm_available
    
    if not is_llm_available():
        print("[SKIP] LLM not available (API key not set)")
        return
    
    print("Generating helpful error message...")
    message = generate_helpful_error_message(
        error_type="INGESTIBILITY_FAILURE",
        error_context={
            "modelId": "test-model-123",
            "target": "https://huggingface.co/test/model",
            "netScore": 0.3,
            "failed_metrics": {
                "license": 0.2,
                "ramp_up": 0.4
            }
        },
        user_action="Attempting to rate model with enforce=true"
    )
    
    if message:
        print(f"\n[RESULT] Generated error message:")
        print(f"  {message}")
    else:
        print("[FAIL] LLM returned None")


def test_integration_license_check():
    """Test LLM integration with license compatibility service."""
    print("\n" + "="*60)
    print("Test: Integration with License Compatibility Service")
    print("="*60)
    
    from services.license_compatibility import check_license_compatibility
    from services.llm_service import is_llm_available
    
    if not is_llm_available():
        print("[SKIP] LLM not available (API key not set)")
        return
    
    # Test with licenses that rule-based checking might be uncertain about
    print("Testing license compatibility check...")
    result = check_license_compatibility(
        model_license="mit",
        github_license="apache-2",
        use_case="fine-tune+inference"
    )
    
    print(f"\n[RESULT]")
    print(f"  Compatible: {result.get('compatible', 'Unknown')}")
    print(f"  LLM Enhanced: {result.get('llm_enhanced', False)}")
    print(f"  Reason: {result.get('reason', 'N/A')[:100]}...")


def interactive_test():
    """Interactive test menu."""
    print("\n" + "="*60)
    print("LLM Integration Manual Test")
    print("="*60)
    
    from services.llm_service import is_llm_available
    
    print(f"\nLLM Status: {'Available' if is_llm_available() else 'Not Available (API key not set)'}")
    
    if not is_llm_available():
        print("\nTo enable LLM features, set GEN_AI_STUDIO_API_KEY in .env file")
        return
    
    tests = {
        "1": ("License Compatibility Analysis", test_license_compatibility),
        "2": ("Model Card Keyword Extraction", test_model_card_keywords),
        "3": ("Error Message Generation", test_error_message),
        "4": ("License Service Integration", test_integration_license_check),
        "5": ("Run All Tests", None),
    }
    
    print("\nAvailable Tests:")
    for key, (name, _) in tests.items():
        print(f"  {key}. {name}")
    print("  q. Quit")
    
    choice = input("\nSelect test (1-5, q): ").strip().lower()
    
    if choice == "q":
        return
    elif choice == "5":
        for key, (name, func) in tests.items():
            if func:
                func()
    elif choice in tests:
        name, func = tests[choice]
        if func:
            func()
        else:
            print("Invalid test")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    try:
        interactive_test()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


