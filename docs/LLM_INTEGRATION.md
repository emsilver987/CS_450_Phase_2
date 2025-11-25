# LLM Integration for Phase 2

## Overview

This document describes the LLM (Large Language Model) integration in Phase 2 of the CS 450 project. LLMs are used to enhance various aspects of the system while maintaining simplicity and avoiding unnecessary complexity.

## Requirements

As specified in the Phase 2 requirements:
- **Must use** LLMs to satisfy some of the LLM integration requirements
- **Must use** LLMs to assist implementation
- **Can use** LLMs in other parts (e.g., modeling, etc.)

## Implementation Strategy

We've integrated LLMs in a **simple, focused way** that adds value without overcomplicating the system:

1. **License Compatibility Analysis** - LLM assists with complex license texts when rule-based checking is uncertain
2. **Model Card Search** - LLM provides semantic search capabilities for better model discovery
3. **Error Message Generation** - LLM generates more helpful, user-friendly error messages

## LLM Service

### Location
`src/services/llm_service.py`

### API Integration
- Uses **Purdue GenAI Studio API** (configurable via environment variables)
- Default model: `llama3.2:latest`
- API URL: `https://genai.rcac.purdue.edu/api/v1/chat/completions`

### Configuration

**Option 1: Using .env file (Recommended for local development)**

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key:
   ```bash
   GEN_AI_STUDIO_API_KEY=your_api_key_here
   ```

3. The `.env` file is automatically loaded when the LLM service is imported (if `python-dotenv` is installed).

**Option 2: Environment variables**

Set the following environment variable:
```bash
# Windows PowerShell
$env:GEN_AI_STUDIO_API_KEY="your_api_key_here"

# Windows CMD
set GEN_AI_STUDIO_API_KEY=your_api_key_here

# Linux/Mac
export GEN_AI_STUDIO_API_KEY="your_api_key_here"

# Alternative variable name (both are supported):
export PURDUE_GENAI_API_KEY="your_api_key_here"
```

**Optional configuration:**
```bash
export PURDUE_GENAI_API_URL="https://genai.rcac.purdue.edu/api/v1/chat/completions"
export PURDUE_GENAI_MODEL="llama3.2:latest"
```

**Note**: The `.env` file is in `.gitignore` and will not be committed to version control. Always keep your API keys secure!

### Features

#### 1. License Compatibility Analysis
**Function**: `analyze_license_compatibility()`

**Purpose**: When rule-based license checking cannot determine compatibility (e.g., for unusual license combinations), the LLM analyzes the full license texts to provide a compatibility assessment.

**Usage**: Automatically called as a fallback in `check_license_compatibility()` when rule-based checking is uncertain.

**Example**:
```python
from src.services.llm_service import analyze_license_compatibility

result = analyze_license_compatibility(
    model_license_text="Full MIT license text...",
    github_license_text="Full Apache 2.0 license text...",
    use_case="fine-tune+inference"
)
# Returns: {"compatible": True/False, "reason": "...", "restrictions": [...]}
```

#### 2. Model Card Semantic Search
**Function**: `extract_model_card_keywords()`

**Purpose**: Extracts semantic keywords from model card content to enable better search functionality. When a regex search doesn't match, the LLM can identify semantically related content.

**Usage**: Automatically used in `search_model_card_content()` as a fallback when regex matching fails.

**Example**:
```python
from src.services.llm_service import extract_model_card_keywords

keywords = extract_model_card_keywords("Model card text...")
# Returns: ["transformer", "NLP", "BERT", "text classification", ...]
```

#### 3. Error Message Generation
**Function**: `generate_helpful_error_message()`

**Purpose**: Generates user-friendly, actionable error messages that explain what went wrong and suggest solutions.

**Usage**: Used in error handling throughout the system, particularly in the rating endpoint.

**Example**:
```python
from src.services.llm_service import generate_helpful_error_message

message = generate_helpful_error_message(
    error_type="INGESTIBILITY_FAILURE",
    error_context={"modelId": "model-123", "failed_metrics": {...}},
    user_action="Attempting to rate model with enforce=true"
)
```

#### 4. Lineage Analysis (Future Enhancement)
**Function**: `analyze_lineage_config()`

**Purpose**: Analyzes complex config.json files to extract parent model information and lineage relationships.

**Status**: Implemented but not yet integrated into the main lineage flow.

## Integration Points

### 1. License Compatibility Service
**File**: `src/services/license_compatibility.py`

**Integration**: LLM is called as a fallback when rule-based checking cannot determine compatibility (line ~381-388).

**Behavior**:
- Rule-based checking runs first (fast, deterministic)
- If uncertain, LLM analysis is attempted
- If LLM is unavailable, falls back to default "cannot determine" response
- Results are marked with `"llm_enhanced": true` when LLM is used

### 2. Model Search Service
**File**: `src/services/s3_service.py`

**Integration**: LLM semantic search is used as a fallback in `search_model_card_content()` when regex matching fails.

**Behavior**:
- Regex pattern matching runs first
- If no match, LLM extracts keywords from model card
- Semantic matching is performed between query and keywords
- Returns `True` if semantic match is found

### 3. Rating Service
**File**: `src/services/rating.py`

**Integration**: LLM generates helpful error messages when ingestibility checks fail.

**Behavior**:
- Standard error message is generated
- If LLM is available, it enhances the message with context
- Enhanced message provides actionable guidance to users

## Design Principles

1. **Graceful Degradation**: All LLM features have fallbacks. If LLM is unavailable, the system continues to work using rule-based methods.

2. **Performance**: LLM calls are rate-limited (1 second between requests) to avoid overwhelming the API.

3. **Simplicity**: LLM integration is focused on specific, high-value use cases rather than trying to replace all logic.

4. **Transparency**: LLM-enhanced results are marked so users know when LLM analysis was used.

5. **Error Handling**: All LLM calls are wrapped in try-except blocks to prevent failures from breaking core functionality.

## Testing

To test LLM integration:

1. **Set API Key**:
   ```bash
   export GEN_AI_STUDIO_API_KEY="your_key"
   ```

2. **Test License Compatibility**:
   - Try checking compatibility for unusual license combinations
   - LLM will be used when rule-based checking is uncertain

3. **Test Model Search**:
   - Search for models using natural language queries
   - LLM semantic matching will help find relevant models

4. **Test Error Messages**:
   - Trigger an ingestibility failure
   - Check that error messages are helpful and actionable

## Future Enhancements

Potential areas for additional LLM integration (if needed):

1. **Lineage Graph Analysis**: Use LLM to parse complex config.json files and extract parent relationships
2. **Model Description Generation**: Auto-generate model descriptions from code and metadata
3. **API Documentation**: Generate API documentation from code comments
4. **Test Case Generation**: Generate test cases from function signatures

## Role of LLMs in Engineering Process

LLMs are used in Phase 2 to:

1. **Assist Implementation**: 
   - Help with complex license analysis
   - Improve search functionality
   - Generate better error messages

2. **Enhance User Experience**:
   - More helpful error messages
   - Better model discovery through semantic search
   - More accurate license compatibility assessment

3. **Support Development**:
   - Code can be enhanced with LLM assistance (documentation, error handling)
   - Complex parsing tasks can leverage LLM understanding

## Limitations

1. **API Dependency**: LLM features require API key and network access
2. **Rate Limiting**: API calls are rate-limited to 1 per second
3. **Cost**: API usage may have costs (check Purdue GenAI Studio pricing)
4. **Latency**: LLM calls add latency (typically 1-3 seconds)
5. **Fallback Required**: All features must work without LLM

## Conclusion

The LLM integration in Phase 2 is designed to be **simple, focused, and valuable**. It enhances specific areas where LLM capabilities add clear value (license analysis, semantic search, error messages) without overcomplicating the system. All features gracefully degrade when LLM is unavailable, ensuring the system remains functional and reliable.

