# Manual Testing Guide for LLM Integration

## Quick Start

### Option 1: Interactive Test Script (Recommended)

Run the interactive test script:

```bash
python test_llm_manual.py
```

This will show you a menu to test different LLM features:
1. License Compatibility Analysis
2. Model Card Keyword Extraction
3. Error Message Generation
4. License Service Integration
5. Run All Tests

### Option 2: Python REPL

Open a Python REPL and test directly:

```python
# Start Python
python

# Import the LLM service
from src.services.llm_service import (
    is_llm_available,
    analyze_license_compatibility,
    extract_model_card_keywords,
    generate_helpful_error_message
)

# Check if LLM is available
print(f"LLM Available: {is_llm_available()}")

# Test license compatibility
result = analyze_license_compatibility(
    model_license_text="MIT License...",
    github_license_text="Apache License 2.0...",
    use_case="fine-tune+inference"
)
print(result)

# Test keyword extraction
keywords = extract_model_card_keywords("BERT model for NLP tasks...")
print(keywords)

# Test error message generation
message = generate_helpful_error_message(
    error_type="INGESTIBILITY_FAILURE",
    error_context={"modelId": "test", "failed_metrics": {"license": 0.2}},
    user_action="Rating model"
)
print(message)
```

## Testing Through the Application

### 1. Test License Compatibility Endpoint

Start the application:
```bash
python -m src.index
```

Then test the license check endpoint (if you have a model uploaded):

```bash
# Using curl
curl -X POST "http://localhost:3000/api/artifact/model/{modelId}/license-check" \
  -H "Content-Type: application/json" \
  -d '{
    "github_url": "https://github.com/example/repo",
    "use_case": "fine-tune+inference"
  }'
```

The LLM will be used automatically when rule-based checking is uncertain.

### 2. Test Model Card Search

Test semantic search through the directory endpoint:

```bash
# Search for models (LLM will help with semantic matching)
curl "http://localhost:3000/api/packages?model_regex=transformer|NLP|BERT"
```

The LLM provides semantic search as a fallback when regex doesn't match.

### 3. Test Error Messages

Trigger an ingestibility failure to see LLM-enhanced error messages:

```bash
# Rate a model with enforce=true (will fail if scores are low)
curl -X POST "http://localhost:3000/api/registry/models/{modelId}/rate" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "https://huggingface.co/test/model",
    "enforce": true
  }'
```

If the model fails ingestibility checks, the error message will be enhanced by LLM.

## Testing Individual Functions

### Test License Compatibility Function

```python
from src.services.llm_service import analyze_license_compatibility

# Test with complex licenses
result = analyze_license_compatibility(
    model_license_text="Full MIT license text here...",
    github_license_text="Full Apache 2.0 license text here...",
    use_case="fine-tune+inference"
)

print(f"Compatible: {result['compatible']}")
print(f"Reason: {result['reason']}")
```

### Test Keyword Extraction

```python
from src.services.llm_service import extract_model_card_keywords

model_card = """
# My Model
This is a transformer model for text classification.
It uses BERT architecture and achieves 95% accuracy.
"""

keywords = extract_model_card_keywords(model_card)
print(f"Keywords: {keywords}")
```

### Test Error Message Generation

```python
from src.services.llm_service import generate_helpful_error_message

message = generate_helpful_error_message(
    error_type="INGESTIBILITY_FAILURE",
    error_context={
        "modelId": "my-model",
        "failed_metrics": {"license": 0.2, "ramp_up": 0.3}
    },
    user_action="Trying to rate model"
)

print(message)
```

## Testing Integration Points

### Test License Compatibility Service Integration

```python
from src.services.license_compatibility import check_license_compatibility

# This will use LLM as fallback when rule-based checking is uncertain
result = check_license_compatibility(
    model_license="mit",
    github_license="apache-2",
    use_case="fine-tune+inference"
)

# Check if LLM was used
if result.get("llm_enhanced"):
    print("LLM was used for this analysis")
```

### Test Model Card Search Integration

The LLM is automatically used in `search_model_card_content()` when:
1. Regex pattern matching fails
2. LLM is available
3. Model card content exists

To test, try searching for models with natural language queries that don't match exact text.

## Verification Checklist

- [ ] LLM service imports without errors
- [ ] API key is loaded (check with `is_llm_available()`)
- [ ] License compatibility analysis returns results
- [ ] Keyword extraction returns a list of keywords
- [ ] Error message generation creates helpful messages
- [ ] Integration with license service works
- [ ] LLM-enhanced results are marked with `llm_enhanced: true`

## Troubleshooting

### LLM Not Available

If `is_llm_available()` returns `False`:
1. Check that `.env` file exists in project root
2. Verify `GEN_AI_STUDIO_API_KEY` is set in `.env`
3. Check that `python-dotenv` is installed: `pip install python-dotenv`

### API Errors

If LLM calls fail:
1. Check your API key is valid
2. Verify network connectivity
3. Check API rate limits (1 request per second)
4. Look for error messages in logs

### No LLM Enhancement

If results don't show `llm_enhanced: true`:
- LLM is only used as a fallback in certain cases
- For license compatibility: only when rule-based checking is uncertain
- For model search: only when regex doesn't match
- This is expected behavior - the system gracefully degrades

## Expected Behavior

1. **With LLM Available**: Features are enhanced, results may include `llm_enhanced: true`
2. **Without LLM**: System works normally using rule-based methods (graceful degradation)
3. **API Failures**: System falls back to rule-based methods automatically

