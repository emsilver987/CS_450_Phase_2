# How to Use the LLM Service

## Quick Start

### 1. Setup API Key

First, set your Purdue GenAI Studio API key:

**Option A: Using .env file (Recommended)**
```bash
# Create or edit .env file in project root
GEN_AI_STUDIO_API_KEY=your_api_key_here
```

**Option B: Environment Variable**
```powershell
# Windows PowerShell
$env:GEN_AI_STUDIO_API_KEY="your_api_key_here"

# Windows CMD
set GEN_AI_STUDIO_API_KEY=your_api_key_here

# Linux/Mac
export GEN_AI_STUDIO_API_KEY="your_api_key_here"
```

### 2. Verify Setup

```python
from src.services.llm_service import is_llm_available

if is_llm_available():
    print("✅ LLM is ready to use!")
else:
    print("❌ API key not found. Set GEN_AI_STUDIO_API_KEY")
```

---

## Direct Usage Examples

### 1. License Compatibility Analysis

Use this when you need to check if two licenses are compatible:

```python
from src.services.llm_service import analyze_license_compatibility

# Example: Check if MIT and Apache licenses are compatible
result = analyze_license_compatibility(
    model_license_text="""
    MIT License
    
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files...
    """,
    github_license_text="""
    Apache License 2.0
    
    Licensed under the Apache License, Version 2.0...
    """,
    use_case="fine-tune+inference"  # or "inference-only", "commercial-use", etc.
)

if result:
    print(f"Compatible: {result['compatible']}")
    print(f"Reason: {result['reason']}")
    print(f"Restrictions: {result.get('restrictions', [])}")
else:
    print("LLM unavailable or API call failed")
```

**Output:**
```python
{
    "compatible": True,
    "reason": "Both licenses are permissive and allow for free use...",
    "restrictions": []
}
```

---

### 2. Extract Keywords from Model Cards

Extract semantic keywords for better search functionality:

```python
from src.services.llm_service import extract_model_card_keywords

model_card_text = """
# BERT Base Model

BERT (Bidirectional Encoder Representations from Transformers) is a 
transformer-based model for natural language processing. This model can be 
used for text classification, question answering, and named entity recognition.

## Performance
Achieves state-of-the-art results on GLUE benchmark.
"""

keywords = extract_model_card_keywords(model_card_text)

if keywords:
    print(f"Extracted {len(keywords)} keywords:")
    print(keywords)
    # Output: ["transformer", "NLP", "BERT", "text classification", 
    #          "question answering", "GLUE benchmark", ...]
else:
    print("LLM unavailable or API call failed")
```

---

### 3. Generate Helpful Error Messages

Create user-friendly error messages:

```python
from src.services.llm_service import generate_helpful_error_message

error_message = generate_helpful_error_message(
    error_type="INGESTIBILITY_FAILURE",
    error_context={
        "modelId": "my-model-123",
        "target": "https://huggingface.co/user/model",
        "netScore": 0.3,
        "failed_metrics": {
            "license": 0.2,
            "ramp_up": 0.4
        }
    },
    user_action="Attempting to rate model with enforce=true"
)

if error_message:
    print(error_message)
else:
    print("LLM unavailable, using default error message")
```

**Example Output:**
```
An issue occurred while processing your rating request for model 'my-model-123'. 
The model failed ingestibility checks because:
- License metric scored 0.2 (below threshold)
- Ramp-up time metric scored 0.4 (below threshold)

To resolve this:
1. Ensure the model has a compatible license
2. Improve documentation to reduce ramp-up time
3. Try rating without enforce=true to see detailed scores
```

---

### 4. Analyze Model Lineage from Config

Extract parent model information from config.json:

```python
from src.services.llm_service import analyze_lineage_config

config = {
    "_name_or_path": "bert-base-uncased",
    "model_type": "bert",
    "base_model_name_or_path": "bert-base-uncased",
    "architectures": ["BertForSequenceClassification"]
}

lineage_info = analyze_lineage_config(config)

if lineage_info:
    print(f"Parent Models: {lineage_info.get('parent_models', [])}")
    print(f"Base Architecture: {lineage_info.get('base_architecture', 'N/A')}")
    print(f"Notes: {lineage_info.get('lineage_notes', 'N/A')}")
```

---

## Automatic Integration (No Code Needed!)

The LLM is **automatically used** in these places:

### 1. License Compatibility Service

When you use `check_license_compatibility()`, the LLM is automatically called as a fallback when rule-based checking is uncertain:

```python
from src.services.license_compatibility import check_license_compatibility

result = check_license_compatibility(
    model_license="mit",
    github_license="apache-2",
    use_case="fine-tune+inference"
)

# LLM is used automatically if needed
if result.get("llm_enhanced"):
    print("✅ Used LLM for this analysis")
```

### 2. Model Search

When searching for models, LLM provides semantic search as a fallback:

```python
# This happens automatically in the search functionality
# When regex doesn't match, LLM extracts keywords and does semantic matching
```

### 3. Error Handling

Error messages are automatically enhanced with LLM when available:

```python
# In your error handling code, just use the service normally
# LLM enhancement happens automatically if available
```

---

## Complete Example Script

Here's a complete example showing all features:

```python
#!/usr/bin/env python3
"""Example: Using the LLM Service"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.llm_service import (
    is_llm_available,
    analyze_license_compatibility,
    extract_model_card_keywords,
    generate_helpful_error_message,
    analyze_lineage_config
)

def main():
    # Check if LLM is available
    if not is_llm_available():
        print("❌ LLM not available. Set GEN_AI_STUDIO_API_KEY")
        return
    
    print("✅ LLM is available!\n")
    
    # Example 1: License Compatibility
    print("=" * 60)
    print("Example 1: License Compatibility Analysis")
    print("=" * 60)
    
    result = analyze_license_compatibility(
        model_license_text="MIT License - Permission is hereby granted...",
        github_license_text="Apache License 2.0 - Licensed under...",
        use_case="fine-tune+inference"
    )
    
    if result:
        print(f"✅ Compatible: {result['compatible']}")
        print(f"   Reason: {result['reason'][:100]}...")
    
    # Example 2: Keyword Extraction
    print("\n" + "=" * 60)
    print("Example 2: Model Card Keyword Extraction")
    print("=" * 60)
    
    keywords = extract_model_card_keywords(
        "BERT model for NLP tasks including text classification and sentiment analysis"
    )
    
    if keywords:
        print(f"✅ Extracted keywords: {', '.join(keywords[:5])}...")
    
    # Example 3: Error Message Generation
    print("\n" + "=" * 60)
    print("Example 3: Error Message Generation")
    print("=" * 60)
    
    message = generate_helpful_error_message(
        error_type="INGESTIBILITY_FAILURE",
        error_context={"modelId": "test-model", "failed_metrics": {"license": 0.2}},
        user_action="Rating model"
    )
    
    if message:
        print(f"✅ Generated message: {message[:100]}...")
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

---

## Best Practices

### 1. Always Check Availability

```python
from src.services.llm_service import is_llm_available

if is_llm_available():
    result = analyze_license_compatibility(...)
    if result:
        # Use LLM result
        pass
    else:
        # Fallback to default behavior
        pass
else:
    # Use rule-based fallback
    pass
```

### 2. Handle None Returns

All LLM functions return `None` if:
- API key is not set
- API call fails
- Network error occurs
- Response parsing fails

Always check for `None`:

```python
result = analyze_license_compatibility(...)
if result:
    # Use result
    pass
else:
    # Handle fallback
    pass
```

### 3. Rate Limiting

The service automatically rate-limits to 1 request per second. You don't need to worry about this, but be aware that:
- Multiple rapid calls will be automatically delayed
- Each call may take 1-3 seconds (API latency + rate limiting)

### 4. Error Handling

The LLM service is designed to fail gracefully:

```python
try:
    result = analyze_license_compatibility(...)
    if result:
        # Use LLM result
        use_llm_result(result)
    else:
        # Fallback to rule-based
        use_rule_based_fallback()
except Exception as e:
    # Even if something unexpected happens, fallback
    logger.warning(f"LLM error: {e}")
    use_rule_based_fallback()
```

---

## Testing

Run the test scripts to verify everything works:

```bash
# Integration test (uses real API)
python test_llm_integration.py

# Simple test
python test_llm_simple.py

# Unit tests (mocked API)
pytest tests/unit/test_llm_service.py -v
```

---

## Troubleshooting

### LLM Not Available

**Problem:** `is_llm_available()` returns `False`

**Solutions:**
1. Check `.env` file exists and has `GEN_AI_STUDIO_API_KEY`
2. Verify environment variable is set: `echo $GEN_AI_STUDIO_API_KEY`
3. Restart your Python process after setting the variable
4. Check that `python-dotenv` is installed: `pip install python-dotenv`

### API Calls Return None

**Problem:** Functions return `None` even with API key set

**Solutions:**
1. Check your API key is valid
2. Verify network connectivity
3. Check API rate limits (1 request/second)
4. Look at logs for error messages
5. Test API directly with curl:

```bash
curl -X POST "https://genai.rcac.purdue.edu/api/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:latest", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Slow Response Times

**Expected:** Each LLM call takes 1-3 seconds due to:
- API latency
- Rate limiting (1 second between requests)
- Model inference time

This is normal behavior. The service is designed for occasional use, not high-frequency calls.

---

## Summary

The LLM service provides four main functions:

1. **`analyze_license_compatibility()`** - Analyze license compatibility
2. **`extract_model_card_keywords()`** - Extract keywords from model cards
3. **`generate_helpful_error_message()`** - Generate user-friendly error messages
4. **`analyze_lineage_config()`** - Extract lineage from config files

All functions:
- Return `None` if LLM is unavailable (graceful degradation)
- Are automatically rate-limited
- Handle errors gracefully
- Can be used directly or are integrated into existing services

For more details, see `docs/LLM_INTEGRATION.md`





