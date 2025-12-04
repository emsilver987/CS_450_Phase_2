# Performance Track: Triggering and Expected Measurements

## Overview

This document explains how to trigger the performance track workload and what measurements/outputs are expected, based on the ACME Corporation requirements and the OpenAPI specification.

## How to Trigger Performance Track

### 1. Via Health Dashboard (Recommended)

The performance workload is **triggerable from the system health dashboard**, as required by the baseline requirements. This is accessible through the `/health/components` endpoint.

**Step 1: Check Health Dashboard**
```bash
GET /health/components
```

This will show the "performance" component with its current status and metrics. The component description indicates:
- Workload can be triggered via `POST /health/performance/workload`
- Results retrieved via `GET /health/performance/results/{run_id}`

**Step 2: Trigger Workload**
```bash
POST /health/performance/workload
Content-Type: application/json

{
  "num_clients": 100,
  "model_id": "arnir0/Tiny-LLM",
  "duration_seconds": 300
}
```

**Response (202 Accepted)**:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "estimated_completion": "2024-01-15T10:05:00Z"
}
```

The workload executes **asynchronously** - the endpoint returns immediately with a `run_id` for tracking.

**Step 3: Retrieve Results**
```bash
GET /health/performance/results/{run_id}
```

### 2. Direct API Call

You can also trigger the workload directly via the API endpoint without going through the health dashboard first.

## Expected Measurements/Output

### Required Measurements (ACME Corporation Requirements)

The system measures the following metrics when 100 clients simultaneously download Tiny-LLM from a registry containing 500 distinct models:

1. **Throughput** (bytes/sec, MB/sec)
   - Total bytes transferred divided by total duration
   - Example: 37.48 MB/sec

2. **Mean Latency** (milliseconds)
   - Average request latency across all 100 requests
   - Example: 51,257.91 ms (51.26 seconds)

3. **Median Latency** (milliseconds)
   - 50th percentile latency
   - Example: 52,931.20 ms (52.93 seconds)

4. **99th Percentile (P99) Latency** (milliseconds)
   - Tail latency metric - 99% of requests complete within this time
   - Example: 63,174.26 ms (63.17 seconds)

### Output Format

The `GET /health/performance/results/{run_id}` endpoint returns a comprehensive results object:

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:01:03Z",
  "metrics": {
    "throughput": {
      "requests_per_second": 1.58,
      "bytes_per_second": 39296263.99
    },
    "latency": {
      "mean_ms": 51257.91,
      "median_ms": 52931.20,
      "p99_ms": 63174.26,
      "min_ms": 12706.16,
      "max_ms": 63189.94
    },
    "error_rate": 0.0,
    "total_requests": 100,
    "total_bytes": 2483400900
  }
}
```

**Note**: The response includes the required measurements (throughput, mean/median/P99 latency) in the `metrics` object. Additional summary statistics are available through the workload status stored internally.

### Additional Metrics Provided

Beyond the required measurements, the system also provides:
- **Min/Max Latency**: Fastest and slowest request latencies
- **Success Rate**: Percentage of successful requests (should be 100%)
- **Total Bytes Transferred**: Total data downloaded
- **Requests per Second**: Throughput in terms of requests
- **Error Rate**: Percentage of failed requests

## Experimental Design

### Workload Specification

**Objective**: Measure system performance when 100 concurrent clients simultaneously download a copy of the Tiny-LLM model from a registry containing 500 distinct models.

**Test Configuration**:
- **Number of Concurrent Clients**: 100
- **Target Model**: Tiny-LLM (ingested from https://huggingface.co/arnir0/Tiny-LLM)
- **Model Size**: ~24.8 MB (24,834,009 bytes)
- **Registry Size**: 500 distinct models stored in S3
- **Download Endpoint**: `/performance/{model_id}/{version}/model.zip`
- **Model ID Format**: `arnir0_Tiny-LLM` (sanitized from HuggingFace format)
- **Version**: `main`

### Infrastructure Setup

**System Components**:
- **Compute**: FastAPI application running on ECS Fargate or AWS Lambda (configurable via `COMPUTE_BACKEND` environment variable)
- **Storage**: Amazon S3 (model files stored at `performance/` prefix)
- **Metadata**: Amazon DynamoDB (model metadata)
- **API**: FastAPI service exposing download endpoints
- **Load Generation**: Custom async load generator using `aiohttp`

**Registry Population**:
- Use `scripts/populate_registry.py --performance` to populate registry
- Tiny-LLM model: Full download including model binary (required for performance testing)
- 499 additional models: Essential files only (config, README) for registry population
- All models stored in S3 under `performance/` prefix for performance testing isolation

## Measurement Methodology

### Black-Box Measurements (External Perspective)

**What**: Measurements taken from the client's perspective, without knowledge of internal system implementation.

**How**:
- Load generator makes HTTP GET requests to download endpoint
- Each request measured from client perspective:
  - Request start timestamp
  - Response completion timestamp
  - Latency = completion - start (milliseconds)
  - Bytes transferred (from response body length)
  - HTTP status code
- All 100 requests initiated simultaneously using `asyncio.gather()`
- Metrics collected per-request, then aggregated

**Metrics Collected**:
- Request latency (end-to-end)
- Bytes transferred per request
- HTTP status codes
- Success/failure rates

**Why Black-Box**: Provides realistic user experience metrics without requiring internal system access. Represents what ACME Corporation would observe when monitoring their system.

### White-Box Measurements (Internal Component Instrumentation)

**What**: Measurements taken from within the system, instrumenting individual components.

**How**:
- **S3 Download Latency**: Time spent in `s3.get_object()` operation
- **Request Processing Time**: Time spent in FastAPI endpoint handler
- **Connection Pool Metrics**: Monitor boto3 connection pool utilization
- **Thread Pool Metrics**: Monitor executor queue depth
- **Server Logs**: Detailed logging of request processing patterns

**Metrics Collected**:
- Component-level latencies (S3, API handler, etc.)
- Resource utilization (connection pools, thread pools)
- Internal processing times
- Queue depths and wait times

**Why White-Box**: Enables identification of specific bottlenecks within the system architecture. Critical for optimization work.

### Combined Analysis

**Black-Box + White-Box Together**:
- Black-box identifies **what** the problem is (e.g., "all requests timeout")
- White-box identifies **where** the problem is (e.g., "S3 connection pool exhausted")
- Together they enable **root cause analysis** and **targeted optimization**

## Performance Bottlenecks: Identification and Optimization

### Bottleneck #1: Synchronous Endpoint Blocking Event Loop

**How Found**:
- **Black-Box**: All 100 requests timed out (300 second timeout)
- **White-Box**: Server logs showed only 1 request processing at a time
- **Root Cause**: Endpoint was synchronous, blocking FastAPI's async event loop

**Optimization**: Converted endpoint to async (`async def`) and used `run_in_executor()` for blocking S3 operations

**Effect**: Enabled concurrent request processing

### Bottleneck #2: Insufficient Thread Pool Capacity

**How Found**:
- **Black-Box**: Some requests succeeded, but processing was sequential
- **White-Box**: Code analysis revealed default executor (~32 workers) insufficient for 100 concurrent requests
- **Root Cause**: Thread pool executor had limited capacity

**Optimization**: Created custom thread pool executor with 100 workers

**Effect**: Enabled true parallelism for blocking I/O operations

### Bottleneck #3: S3 Connection Pool Size Limitation

**How Found**:
- **Black-Box**: Requests still experiencing delays
- **White-Box**: Warning logs: "Connection pool is full (size: 10)"
- **Root Cause**: boto3 default connection pool (10 connections) insufficient for 100 concurrent requests

**Optimization**: Increased S3 client connection pool to 150 connections

**Effect**: Eliminated connection queue bottleneck

### Combined Effect

**Before Optimizations**:
- Success Rate: 0% (all requests timed out)
- Throughput: 0 MB/sec
- Mean Latency: 300.93 seconds (timeout)
- P99 Latency: 301.08 seconds (timeout)

**After All Optimizations**:
- Success Rate: 100%
- Throughput: 37.48 MB/sec
- Mean Latency: 51.26 seconds (83% reduction)
- P99 Latency: 63.17 seconds (79% reduction)
- Total Duration: 63.20 seconds (79% reduction)

## Integration with Health Dashboard

The performance component appears in `/health/components` response:

```json
{
  "components": [
    {
      "id": "performance",
      "status": "ok",
      "display_name": "Performance Testing",
      "description": "Performance testing component for measuring system throughput and latency. Workload can be triggered via POST /health/performance/workload. Results retrieved via GET /health/performance/results/{run_id}.",
      "metrics": {
        "latest_run_id": "550e8400-e29b-41d4-a716-446655440000",
        "latest_throughput_mbps": 37.48,
        "latest_p99_latency_ms": 63174.26,
        "latest_mean_latency_ms": 51257.91,
        "latest_median_latency_ms": 52931.20,
        "latest_success_rate": 100.0,
        "total_runs_completed": 1,
        "last_run_started_at": "2024-01-15T10:00:00Z",
        "last_run_completed_at": "2024-01-15T10:01:03Z"
      }
    }
  ]
}
```

This allows the health dashboard to:
1. Display current performance status
2. Show latest performance metrics
3. Provide links/instructions to trigger new workloads
4. Monitor performance over time

## References

- **OpenAPI Spec**: `/health/components` endpoint (NON-BASELINE) - lines 42-72
- **Assignment Requirement**: "This workload should be triggerable from your team's system health dashboard, completed as part of the baseline requirements."
- **Performance Papers**:
  - https://dl.acm.org/doi/abs/10.1145/3213770
  - https://gernot-heiser.org/benchmarking-crimes.html#sign
- **Detailed Bottleneck Analysis**: See `PERFORMANCE_BOTTLENECKS.md`

