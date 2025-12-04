# What the LLM is Doing in the API

## Overview

The LLM (Large Language Model) is integrated into your API in **3 main places** to enhance functionality. It works **automatically** as a fallback when rule-based methods can't handle complex cases.

---

## 1. License Compatibility Analysis

### Where it's used:
- **Service**: `src/services/license_compatibility.py`
- **Function**: `check_license_compatibility()`
- **When**: Automatically called when rule-based license checking is uncertain

### What it does:

1. **First**: Rule-based checking runs (fast, deterministic)
   - Checks common license combinations (MIT + Apache, GPL + MIT, etc.)
   - Uses predefined compatibility rules

2. **Then**: If rule-based checking can't determine compatibility, **LLM is called automatically**
   - Analyzes full license texts
   - Considers use case (fine-tune+inference, inference-only, etc.)
   - Provides detailed compatibility assessment

3. **Result**: Returns compatibility result with `"llm_enhanced": true` flag

### Code Flow:
```python
# In license_compatibility.py (line ~382-404)
if rule_based_check_failed:
    if is_llm_available():
        llm_result = analyze_license_compatibility(
            model_license_text=model_license,
            github_license_text=github_license,
            use_case=use_case
        )
        if llm_result:
            result["compatible"] = llm_result["compatible"]
            result["reason"] = f"LLM-assisted analysis: {llm_result['reason']}"
            result["llm_enhanced"] = True  # ← Marks that LLM was used
```

### Example API Usage:
When a user checks license compatibility (through any endpoint that uses `check_license_compatibility()`), the LLM automatically helps if needed:

```json
{
  "compatible": true,
  "reason": "LLM-assisted analysis: Both licenses are permissive...",
  "llm_enhanced": true,
  "restrictions": []
}
```

---

## 2. Model Card Semantic Search

### Where it's used:
- **Service**: `src/services/s3_service.py`
- **Function**: `search_model_card_content()`
- **When**: Automatically called when regex pattern matching fails

### What it does:

1. **First**: Regex pattern matching runs on model card content
   - Fast text search
   - Exact pattern matching

2. **Then**: If regex doesn't match, **LLM is called automatically**
   - Extracts semantic keywords from model cards
   - Performs semantic matching between query and keywords
   - Helps find models even when exact text doesn't match

3. **Result**: Returns `True` if semantic match is found

### Code Flow:
```python
# In s3_service.py (line ~395-420)
if not regex_match:
    if is_llm_available() and model_card_content:
        # Extract keywords using LLM
        model_keywords = extract_model_card_keywords(combined_content)
        
        if model_keywords:
            # Check if query matches any keywords semantically
            for keyword in model_keywords:
                if query_matches_keyword(query, keyword):
                    return True  # Semantic match found!
```

### Example API Usage:
When a user searches for models using `/api/packages?model_regex=transformer`:
- If exact text "transformer" is found → returns immediately (no LLM)
- If not found → LLM extracts keywords like ["transformer", "NLP", "BERT"] → finds semantic match → returns results

---

## 3. Error Message Generation

### Where it's used:
- **Service**: `src/services/rating.py`
- **Function**: `rate_model()` (when ingestibility checks fail)
- **When**: Automatically called when a model fails ingestibility checks with `enforce=true`

### What it does:

1. **First**: Standard error message is generated
   - Basic error: "Failed ingestibility: license=0.2, ramp_up=0.4"

2. **Then**: If LLM is available, **it enhances the error message**
   - Explains what went wrong in simple terms
   - Suggests possible solutions
   - Makes error messages more helpful and actionable

3. **Result**: Returns enhanced error message to user

### Code Flow:
```python
# In rating.py (line ~716-731)
if ingestibility_failed:
    error_message = f"Failed ingestibility: {failures}"
    
    if is_llm_available():
        llm_message = generate_helpful_error_message(
            error_type="INGESTIBILITY_FAILURE",
            error_context={
                "modelId": modelId,
                "target": target,
                "netScore": netScore,
                "failed_metrics": failures
            },
            user_action="Attempting to rate model with enforce=true"
        )
        if llm_message:
            error_message = llm_message  # Use LLM-enhanced message
```

### Example API Usage:
When a user rates a model with `enforce=true` and it fails:

**Without LLM:**
```json
{
  "detail": "Failed ingestibility: license=0.2, ramp_up=0.4"
}
```

**With LLM:**
```json
{
  "detail": "An issue occurred while attempting to rate your model 'my-model-123'. The model failed ingestibility checks because the license metric scored 0.2 (below threshold) and ramp-up time scored 0.4. To resolve this, ensure the model has a compatible license and improve documentation to reduce ramp-up time. Try rating without enforce=true to see detailed scores."
}
```

---

## API Endpoints That Use LLM

### Direct Usage:

1. **Rating Endpoint** (`POST /api/registry/models/{modelId}/rate`)
   - Uses LLM for error messages when ingestibility fails
   - Location: `src/services/rating.py`

2. **Package Search** (`GET /api/packages?model_regex=...`)
   - Uses LLM for semantic search when regex doesn't match
   - Location: `src/services/s3_service.py`

3. **License Compatibility** (used internally by various endpoints)
   - Uses LLM when rule-based checking is uncertain
   - Location: `src/services/license_compatibility.py`

### Indirect Usage:

The LLM is used **automatically** in the background when:
- Users search for models
- Models are rated
- License compatibility is checked
- Any service needs enhanced error messages

---

## How It Works (Technical Flow)

### 1. Automatic Fallback Pattern

All LLM usage follows this pattern:

```python
# Step 1: Try rule-based/fast method first
result = fast_rule_based_method()

# Step 2: If uncertain/failed, try LLM
if result_is_uncertain and is_llm_available():
    llm_result = llm_method()
    if llm_result:
        result = llm_result
        result["llm_enhanced"] = True

# Step 3: If LLM fails, use default fallback
if not result:
    result = default_fallback()
```

### 2. Graceful Degradation

- **If LLM is unavailable**: System continues with rule-based methods
- **If LLM call fails**: Falls back to default behavior
- **No breaking changes**: API always returns a response

### 3. Rate Limiting

- LLM calls are automatically rate-limited to 1 request per second
- Prevents overwhelming the API
- Handled transparently in `llm_service.py`

---

## Example: Complete Request Flow

### Scenario: User searches for "BERT transformer model"

```
1. User Request:
   GET /api/packages?model_regex=transformer

2. API Processing:
   ├─ Try regex search: "transformer" in model cards
   ├─ Found matches? → Return immediately (no LLM)
   └─ No matches? → Call LLM
      ├─ LLM extracts keywords: ["transformer", "NLP", "BERT", ...]
      ├─ Semantic match found? → Return results
      └─ No match? → Return empty results

3. Response:
   {
     "packages": [...],
     "llm_enhanced": false  // or true if LLM was used
   }
```

### Scenario: User rates model with enforce=true, but it fails

```
1. User Request:
   POST /api/registry/models/my-model/rate
   {
     "target": "https://huggingface.co/user/model",
     "enforce": true
   }

2. API Processing:
   ├─ Calculate metrics: license=0.2, ramp_up=0.4
   ├─ Check ingestibility: FAILED (both < 0.5)
   ├─ Generate error message
   │  ├─ Try LLM enhancement
   │  │  └─ LLM generates helpful message
   │  └─ Use LLM message if available
   └─ Return error

3. Response:
   HTTP 422
   {
     "detail": "LLM-enhanced helpful error message..."
   }
```

---

## Key Points

1. **Automatic**: LLM is called automatically - no special API endpoints needed
2. **Transparent**: Results are marked with `"llm_enhanced": true` when LLM is used
3. **Fallback**: Always has a fallback if LLM is unavailable
4. **Non-blocking**: LLM failures don't break the API
5. **Rate-limited**: Automatically rate-limited to prevent API overload

---

## Monitoring LLM Usage

To see when LLM is being used:

1. **Check response flags**: Look for `"llm_enhanced": true` in responses
2. **Check logs**: LLM calls are logged (debug level)
3. **Response times**: LLM calls add 2-5 seconds (normal)

---

## Summary

The LLM enhances your API in 3 ways:

1. **License Analysis** → Helps with complex license compatibility questions
2. **Semantic Search** → Finds models even when exact text doesn't match
3. **Error Messages** → Makes errors more helpful and actionable

All of this happens **automatically** in the background - users don't need to do anything special. The LLM is a smart fallback that makes your API more capable without adding complexity.




