# LLM Summary Metric Documentation

## Overview

The **LLM Summary Metric** is a Phase 2 metric that analyzes package README text using an LLM client to generate human-readable summaries, identify risk flags, and produce a documentation quality score. This metric helps evaluate how well-documented a package is and surfaces potential issues like missing licenses or safety considerations.

## What It Does

The LLM Summary Metric performs three main functions:

1. **Analyzes README Text**: Extracts and processes README content from GitHub repositories or HuggingFace model cards
2. **Generates Summaries**: Creates concise, human-readable summaries (max 200 characters) describing what the package includes
3. **Flags Risks**: Identifies potential issues like missing licenses, installation guides, examples, or safety documentation
4. **Scores Documentation Quality**: Produces a score (0.0-1.0) based on documentation completeness

## How It Works

### Architecture

```
Package README → LLM Client → Analysis → Summary + Flags + Score
```

The metric follows this flow:

1. **Extraction**: The metric extracts `readme_text` from the metadata dictionary
2. **Analysis**: Calls the LLM client (`LLMClient.analyze_readme()`) to analyze the text
3. **Storage**: Stores results in metadata:
   - `llm_summary`: Human-readable summary string
   - `llm_risk_flags`: List of risk indicators
4. **Scoring**: Returns a `MetricValue` with score and latency

### Current Implementation (Stub Mode)

By default, the metric runs in **offline stub mode** for autograder compatibility. The stub implementation uses heuristic keyword matching:

#### Scoring Logic

- **Base Score**: `0.5`
- **Positive Indicators** (+0.1 each):
  - Open source license (MIT/Apache)
  - Installation instructions
  - Usage examples
  - Safety considerations
  - Model card documentation
- **Negative Indicators**:
  - Missing license: `-0.1`
  - Risk flags: `-0.05` per flag

#### Example Scoring

```python
# Well-documented package
README contains: license (MIT), install, examples, safety
Score = 0.5 + 0.1 + 0.1 + 0.1 + 0.1 = 0.9

# Poorly documented package
README missing: license, install, examples
Score = 0.5 - 0.1 - (3 flags × 0.05) = 0.25
```

### Future Implementation (Bedrock Mode)

When `ENABLE_LLM=true` and Bedrock is configured, the metric will:
- Send README text to Amazon Bedrock (e.g., Claude)
- Generate AI-powered summaries
- Identify risks using natural language understanding
- Provide more nuanced analysis than keyword matching

## Integration Points

### Metric Registration

The metric is registered in `src/acmecli/metrics/__init__.py`:

```python
from .llm_summary_metric import LLMSummaryMetric
register(LLMSummaryMetric())
```

### Scoring Integration

The metric contributes **5% weight** to the overall `net_score` calculation in `src/acmecli/scoring.py`:

```python
weights = {
    # ... other metrics ...
    "llm_summary": 0.05,  # LLM-based documentation analysis
}
```

### Output Format

The metric appears in NDJSON reports with these fields:

```json
{
  "llm_summary": 0.9,
  "llm_summary_latency": 8
}
```

## Usage

### Running the Metric

The metric runs automatically when scoring packages:

```bash
./run score urls.txt
```

Or via Python:

```bash
python3 -m src.acmecli.cli score urls.txt
```

### Configuration

#### Offline Mode (Default)

No configuration needed. The metric uses stub implementation:

```bash
# Works offline, no API calls
./run score urls.txt
```

#### LLM Mode (Future)

To enable Bedrock integration (when implemented):

```bash
export ENABLE_LLM=true
# Configure Bedrock credentials
./run score urls.txt
```

## Example Output

### Well-Documented Package

```json
{
  "name": "my-model",
  "llm_summary": 0.9,
  "llm_summary_latency": 8
}
```

**Metadata stored:**
```python
meta["llm_summary"] = "Package includes: Open source license, Installation instructions, Usage examples."
meta["llm_risk_flags"] = ["safety_review_needed"]
```

### Poorly Documented Package

```json
{
  "name": "minimal-model",
  "llm_summary": 0.0,
  "llm_summary_latency": 1
}
```

**Metadata stored:**
```python
meta["llm_summary"] = "No README content available."
meta["llm_risk_flags"] = ["missing_readme", "missing_license", "missing_installation_guide", "missing_examples"]
```

## Files and Components

### Core Files

1. **`src/services/llm_client.py`**
   - `LLMClient` class
   - `analyze_readme()` method
   - Stub and Bedrock implementations

2. **`src/acmecli/metrics/llm_summary_metric.py`**
   - `LLMSummaryMetric` class
   - `score()` method
   - Metric registration

### Integration Points

- **`src/acmecli/metrics/__init__.py`**: Metric registration
- **`src/acmecli/scoring.py`**: Weight configuration
- **`src/acmecli/types.py`**: `ReportRow` dataclass fields
- **`src/acmecli/cli.py`**: CLI integration
- **`src/services/rating.py`**: FastAPI service integration

## Risk Flags

The metric identifies these risk indicators:

- `missing_readme`: No README content found
- `missing_license`: No license information
- `license_review_needed`: License present but not standard (MIT/Apache)
- `missing_installation_guide`: No install/usage instructions
- `missing_examples`: No demo/example code
- `safety_review_needed`: No safety/bias considerations mentioned
- `llm_unavailable`: LLM client failed (fallback case)

## Scoring Details

### Score Calculation

```python
base_score = llm_result["score"]  # From LLM client (0.0-1.0)
risk_penalty = len(risk_flags) * 0.05
final_score = max(0.0, min(1.0, base_score - risk_penalty))
```

### Score Interpretation

- **0.9-1.0**: Excellent documentation (has license, install, examples, safety)
- **0.7-0.8**: Good documentation (missing 1-2 elements)
- **0.5-0.6**: Basic documentation (missing several elements)
- **0.0-0.4**: Poor documentation (missing most elements or no README)

## Autograder Compatibility

The metric is designed to work offline for autograder compatibility:

✅ **Default behavior**: Uses stub implementation (no external calls)  
✅ **Graceful degradation**: Returns neutral score (0.5) if LLM client fails  
✅ **Feature flag controlled**: `ENABLE_LLM` environment variable  
✅ **No hard dependencies**: Works without Bedrock configuration  

## Troubleshooting

### Metric Returns 0.0

**Possible causes:**
- No README text in metadata
- README is too short (< 10 characters)
- All risk flags triggered

**Solution:** Check that handlers are extracting README text correctly.

### Metric Not Appearing in Output

**Possible causes:**
- Metric not registered
- Import error in metrics `__init__.py`

**Solution:** Verify registration in `src/acmecli/metrics/__init__.py`.

### High Latency

**Possible causes:**
- Bedrock API calls (when enabled)
- Large README text processing

**Solution:** Latency is typically < 10ms in stub mode. If using Bedrock, expect 100-500ms.

## Future Enhancements

1. **Bedrock Integration**: Full LLM-powered analysis
2. **Custom Prompts**: Configurable analysis prompts
3. **Multi-language Support**: Analyze READMEs in different languages
4. **Sentiment Analysis**: Detect positive/negative tone
5. **Completeness Scoring**: More granular documentation quality metrics

## Related Documentation

- **`docs/LLM_USAGE.md`**: Overall LLM usage plan for Phase 2
- **`LLM_IMPLEMENTATION_PLAN.md`**: Detailed implementation guide
- **`README.md`**: Project overview and metric reference

## Code Examples

### Using the LLM Client Directly

```python
from services.llm_client import LLMClient

client = LLMClient()
result = client.analyze_readme(readme_text)

print(result["summary"])      # "Package includes: ..."
print(result["risk_flags"])   # ["missing_license", ...]
print(result["score"])        # 0.9
```

### Accessing LLM Results from Metadata

```python
# After scoring
meta = {...}  # Metadata dict

if "llm_summary" in meta:
    summary = meta["llm_summary"]
    flags = meta.get("llm_risk_flags", [])
    print(f"Summary: {summary}")
    print(f"Risks: {flags}")
```

## Summary

The LLM Summary Metric provides:
- ✅ Automated documentation quality assessment
- ✅ Human-readable summaries for UI display
- ✅ Risk flagging for missing documentation
- ✅ Offline compatibility for autograder
- ✅ Future-ready for Bedrock integration

It's a lightweight, feature-flag controlled metric that enhances package evaluation without requiring external dependencies.

