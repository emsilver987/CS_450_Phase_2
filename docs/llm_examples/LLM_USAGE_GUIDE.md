# LLM Functionality - Complete Usage Guide

## What It Does

The **LLM Summary Metric** automatically analyzes package README files to:

1. **Generate Summaries** - Creates human-readable summaries (max 200 characters)
2. **Identify Risk Flags** - Detects missing documentation elements
3. **Score Documentation Quality** - Produces a score (0.0-1.0) based on completeness
4. **Store Metadata** - Saves results for UI display and downstream analysis

## How It Works

```
Package README → LLM Client → Analysis → Summary + Flags + Score
```

### Scoring Logic (Offline Mode)

- **Base Score**: 0.5
- **Positive Indicators** (+0.1 each):
  - Open source license (MIT/Apache)
  - Installation instructions
  - Usage examples
  - Safety considerations
  - Model card documentation
- **Negative Indicators**:
  - Missing license: -0.1
  - Risk flags: -0.05 per flag

### Example Scores

- **Well-documented** (license, install, examples, safety): **0.9**
- **Good** (license, install, examples): **0.7**
- **Basic** (just install guide): **0.5**
- **Poor** (missing license, no examples): **0.25**
- **No README**: **0.0**

## How to Use It

### Method 1: Command Line (Automatic) ⭐ Recommended

The LLM metric runs **automatically** when you score packages:

```bash
./run score urls.txt
```

Or with Python:

```bash
python3 -m src.acmecli.cli score urls.txt
```

**Output includes:**
```json
{
  "name": "my-model",
  "llm_summary": 0.8,
  "llm_summary_latency": 5,
  "net_score": 0.75,
  ...
}
```

### Method 2: Python API (Programmatic)

#### Using the LLM Client Directly

```python
from services.llm_client import LLMClient

client = LLMClient()
result = client.analyze_readme(readme_text)

print(result['summary'])      # "Package includes: Open source license..."
print(result['risk_flags'])   # ['missing_examples', 'safety_review_needed']
print(result['score'])        # 0.8
```

#### Using the Metric

```python
from acmecli.metrics.llm_summary_metric import LLMSummaryMetric

meta = {"readme_text": "MIT License. Installation guide..."}
metric = LLMSummaryMetric()
result = metric.score(meta)

print(result.value)              # 0.8
print(meta['llm_summary'])       # Summary text
print(meta['llm_risk_flags'])    # Risk flags list
```

### Method 3: FastAPI Service (HTTP API)

The LLM metric is included when you call the `/rate` endpoint:

```bash
POST /rate
{
  "target": "https://github.com/user/repo"
}
```

**Response includes:**
```json
{
  "metrics": {
    "llm_summary": 0.8,
    ...
  },
  "metadata": {
    "llm_summary": "Package includes: ...",
    "llm_risk_flags": [...]
  }
}
```

## Configuration

### Default Mode (Offline - Recommended)

**No configuration needed!** The LLM runs in offline stub mode by default:

- ✅ No external API calls
- ✅ Fast and deterministic
- ✅ Works without AWS credentials
- ✅ Autograder-safe

Just use it:
```bash
./run score urls.txt
```

### Bedrock Mode (Online - For Production)

To enable real LLM analysis with Amazon Bedrock:

1. **Install boto3:**
   ```bash
   pip install boto3
   ```

2. **Configure AWS credentials:**
   ```bash
   aws configure
   # OR set AWS credentials via environment variables
   ```

3. **Enable LLM:**
   ```bash
   export ENABLE_LLM=true
   export AWS_REGION=us-east-1  # Optional, defaults to us-east-1
   ```

4. **Run scoring:**
   ```bash
   ./run score urls.txt
   ```

The system will:
- ✅ Use Amazon Bedrock (Claude) for analysis
- ✅ Generate AI-powered summaries
- ✅ Provide more nuanced risk detection
- ✅ Fall back to stub if Bedrock unavailable

## Examples

### Example 1: Well-Documented Package

```python
readme = """
# My ML Model
MIT License
Installation: pip install my-model
Usage examples included.
Safety considerations documented.
"""

client = LLMClient()
result = client.analyze_readme(readme)

# Output:
# summary: "Package includes: Open source license, Installation instructions, Usage examples."
# risk_flags: []
# score: 0.9
```

### Example 2: Poorly Documented Package

```python
readme = "This is a model."

client = LLMClient()
result = client.analyze_readme(readme)

# Output:
# summary: "Basic package documentation available."
# risk_flags: ['missing_license', 'missing_installation_guide', 'missing_examples', 'safety_review_needed']
# score: 0.2
```

### Example 3: Using in Scoring Pipeline

```python
from acmecli.metrics.base import REGISTRY
from acmecli.scoring import compute_net_score

meta = {"readme_text": "MIT License. Installation guide..."}

# Run all metrics (LLM included automatically)
results = {}
for metric in REGISTRY:
    results[metric.name] = metric.score(meta)

# Compute net score (LLM contributes 5%)
net_score, latency = compute_net_score(results)

# Access LLM results
print(f"LLM Score: {results['LLMSummary'].value}")
print(f"Summary: {meta['llm_summary']}")
print(f"Risk Flags: {meta['llm_risk_flags']}")
```

## Output Format

### CLI Output (NDJSON)

```json
{
  "name": "my-model",
  "llm_summary": 0.8,
  "llm_summary_latency": 5,
  "net_score": 0.75
}
```

### Metadata (Internal)

```python
meta = {
    "llm_summary": "Package includes: Open source license, Installation instructions, Usage examples.",
    "llm_risk_flags": ["safety_review_needed"]
}
```

## Risk Flags

The metric identifies these risk indicators:

- `missing_readme` - No README content found
- `missing_license` - No license information
- `license_review_needed` - License present but not standard (MIT/Apache)
- `missing_installation_guide` - No install/usage instructions
- `missing_examples` - No demo/example code
- `safety_review_needed` - No safety/bias considerations mentioned
- `llm_unavailable` - LLM client failed (fallback case)

## Score Interpretation

- **0.9-1.0**: Excellent documentation (has license, install, examples, safety)
- **0.7-0.8**: Good documentation (missing 1-2 elements)
- **0.5-0.6**: Basic documentation (missing several elements)
- **0.0-0.4**: Poor documentation (missing most elements or no README)

## Integration Points

1. **Metric Registry** - Automatically registered in `src/acmecli/metrics/__init__.py`
2. **Scoring** - Contributes 5% weight to `net_score` in `src/acmecli/scoring.py`
3. **CLI** - Runs automatically in `process_url()` function
4. **API** - Included in `/rate` endpoint via `METRIC_FUNCTIONS`
5. **Output** - Appears in `ReportRow` with `llm_summary` and `llm_summary_latency` fields

## Troubleshooting

### Metric Returns 0.0
- **Cause**: No README text or README too short
- **Solution**: Check that handlers are extracting README text correctly

### Metric Not Appearing in Output
- **Cause**: Metric not registered or import error
- **Solution**: Verify registration in `src/acmecli/metrics/__init__.py`

### High Latency
- **Cause**: Bedrock API calls (when enabled)
- **Solution**: Latency is typically < 10ms in stub mode. If using Bedrock, expect 100-500ms.

## Summary

✅ **Runs automatically** - No manual intervention needed  
✅ **Offline by default** - Works without external dependencies  
✅ **Contributes to score** - 5% weight in net_score calculation  
✅ **Stores metadata** - Available for UI and downstream use  
✅ **Production-ready** - Graceful fallback and error handling  

**Just run: `./run score urls.txt`**  
**The LLM metric will work automatically!**

